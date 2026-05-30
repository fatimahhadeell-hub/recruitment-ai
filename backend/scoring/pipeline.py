
import datetime
from bson import ObjectId
from loguru import logger
try:
    from candidate_sheet import update_cv_result
    SHEET_ENABLED = True
except Exception:
    SHEET_ENABLED = False
from database.mongodb import db_manager
from models.schemas import CandidateStatus, ScoringWeights
from scoring.llm_scorer import score_candidate_with_llm

def run_scoring_pipeline() -> dict:
    result = {"scored": 0, "shortlisted": 0, "not_selected": 0, "failed": 0}
    pending = list(db_manager.candidates.find({"status": CandidateStatus.PROCESSING.value}))
    logger.info(f"Scoring pipeline: {len(pending)} candidates with status PROCESSING.")
    for candidate in pending:
        candidate_id = candidate["_id"]
        name         = candidate.get("full_name", "Unknown")
        job_id_str   = candidate.get("job_id", "")
        cv_text      = candidate.get("raw_cv_text", "")
        work_exp     = candidate.get("work_experience", [])
        if not cv_text:
            logger.warning(f"No CV text for {name}. Skipping.")
            result["failed"] += 1
            continue
        try:
            job = db_manager.jobs.find_one({"_id": ObjectId(job_id_str)})
        except Exception:
            job = db_manager.jobs.find_one({"_id": job_id_str})
        if not job:
            logger.error(f"Job not found for candidate {name}. job_id: {job_id_str}")
            result["failed"] += 1
            continue
        weights_data = job.get("scoring_weights", {})
        weights = ScoringWeights(
            education    = weights_data.get("education",    0.20),
            experience   = weights_data.get("experience",   0.25),
            skills       = weights_data.get("skills",       0.20),
            stability    = weights_data.get("stability",    0.10),
            progression  = weights_data.get("progression",  0.10),
            values       = weights_data.get("values",       0.10),
            communication= weights_data.get("communication",0.05),
        )
        threshold = job.get("shortlist_threshold", 65)
        logger.info(f"Scoring candidate: {name}")
        score_doc = score_candidate_with_llm(cv_text, job, weights, work_exp)
        if not score_doc:
            db_manager.candidates.update_one(
                {"_id": candidate_id},
                {"$set": {"status": CandidateStatus.ERROR.value, "error_message": "LLM scoring failed.", "updated_at": datetime.datetime.utcnow()}}
            )
            result["failed"] += 1
            continue
        score_doc.candidate_id = str(candidate_id)
        score_doc.job_id       = job_id_str
        is_shortlisted         = score_doc.final_score >= threshold
        score_doc.is_shortlisted = is_shortlisted
        score_dict = score_doc.model_dump(by_alias=True, exclude_none=True)
        db_manager.scores.update_one(
                {"candidate_id": str(candidate_id), "job_id": job_id_str},
                {"$set": score_dict},
                upsert=True
            )
        new_status = CandidateStatus.SHORTLISTED.value if is_shortlisted else CandidateStatus.NOT_SELECTED.value
        db_manager.candidates.update_one(
            {"_id": candidate_id},
            {"$set": {"final_score": score_doc.final_score, "status": new_status, "updated_at": datetime.datetime.utcnow()}}
        )
        db_manager.jobs.update_one(
            {"_id": job.get("_id")},
            {"$inc": {"shortlisted_count": 1 if is_shortlisted else 0}, "$set": {"updated_at": datetime.datetime.utcnow()}}
        )
        result["scored"] += 1
        if is_shortlisted:
            result["shortlisted"] += 1
            logger.success(f"{name}: {score_doc.final_score}/100 - SHORTLISTED")
        else:
            result["not_selected"] += 1
            logger.info(f"{name}: {score_doc.final_score}/100 - NOT SELECTED")
        # Auto-update candidate Google Sheet
        if SHEET_ENABLED:
            try:
                email = candidate.get("email", "")
                update_cv_result(email, score_doc.final_score, is_shortlisted)
            except Exception as e:
                logger.warning(f"Could not update candidate sheet: {e}")
    logger.info(f"Scoring complete. {result}")
    return result
