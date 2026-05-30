
from fastapi import FastAPI
import uuid
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
from config.settings import settings
from database.mongodb import db_manager

app = FastAPI(
    title="Recruitment AI API",
    description="AI-Powered Automated Recruitment and Candidate Screening System",
    version=settings.APP_VERSION
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8501", "http://127.0.0.1:8501", "http://localhost:8082", "http://127.0.0.1:8082", "http://localhost:8080", "http://127.0.0.1:8080", "http://192.168.18.14:8080", "http://192.168.18.14:8000", "null"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup():
    logger.info("Starting Recruitment AI API...")
    db_manager.connect()
    db_manager.create_indexes()
    # Start background poller - checks for new CVs every 5 minutes
    import threading
    from intake.drive_fetcher import DriveFetcher
    from extraction import process_pending_candidates
    from scoring.pipeline import run_scoring_pipeline
    from notifications import notify_shortlisted_candidates, notify_rejected_candidates, notify_mcq_passed_candidates, notify_mcq_failed_candidates
    from scoring.mcq_scorer import process_mcq_responses
    def background_pipeline():
        import time
        logger.info("Background poller started. Checking every 5 minutes.")
        while True:
            try:
                time.sleep(300)  # Wait 5 minutes
                logger.info("Poller: checking for new CVs...")
                DriveFetcher().run()
                process_pending_candidates()
                run_scoring_pipeline()
                process_mcq_responses()
                notify_shortlisted_candidates()
                notify_rejected_candidates()
                logger.info("Poller: cycle complete.")
            except Exception as e:
                logger.error(f"Poller error: {e}")
    poller_thread = threading.Thread(target=background_pipeline, daemon=True)
    poller_thread.start()
    logger.success("API ready.")

@app.on_event("shutdown")
async def shutdown():
    db_manager.disconnect()
    logger.info("API shut down.")

@app.get("/")
async def root():
    return {"message": "Recruitment AI API", "version": settings.APP_VERSION, "status": "running"}

@app.get("/api/v1/health")
async def health():
    db_connected = db_manager.is_connected()
    stats = db_manager.get_stats() if db_connected else {}
    return {
        "status":       "healthy" if db_connected else "degraded",
        "database":     "connected" if db_connected else "disconnected",
        "stats":        stats
    }

@app.get("/api/v1/jobs")
async def list_jobs():
    jobs = list(db_manager.jobs.find({}))
    for j in jobs:
        j["_id"] = str(j["_id"])
    return {"jobs": jobs, "total": len(jobs)}

@app.post("/api/v1/jobs")
async def create_job(job_data: dict):
    from models.schemas import JobDocument, JobStatus
    import datetime
    job = JobDocument(**job_data)
    doc = job.model_dump(by_alias=True, exclude_none=True)
    result = db_manager.jobs.insert_one(doc)
    return {"message": "Job created", "id": str(result.inserted_id)}

@app.get("/api/v1/jobs/{job_id}/candidates")
async def get_candidates(job_id: str):
    candidates = list(db_manager.candidates.find({"job_id": job_id}))
    for c in candidates:
        c["_id"] = str(c["_id"])
    return {"candidates": candidates, "total": len(candidates)}

@app.get("/api/v1/candidates/{candidate_id}/score")
async def get_score(candidate_id: str):
    score = db_manager.scores.find_one({"candidate_id": candidate_id})
    if not score:
        return {"error": "Score not found"}
    score["_id"] = str(score["_id"])
    return score

@app.post("/api/v1/pipeline/fetch")
async def trigger_fetch():
    from intake.drive_fetcher import DriveFetcher
    fetcher = DriveFetcher()
    result  = fetcher.run()
    return {"message": "Fetch complete", "result": result}

@app.post("/api/v1/pipeline/extract")
async def trigger_extraction():
    from extraction import process_pending_candidates
    result = process_pending_candidates()
    return {"message": "Extraction complete", "result": result}

@app.post("/api/v1/pipeline/score")
async def trigger_scoring():
    from scoring.pipeline import run_scoring_pipeline
    result = run_scoring_pipeline()
    return {"message": "Scoring complete", "result": result}

@app.post("/api/v1/pipeline/mcq")
async def pipeline_mcq():
    from scoring.mcq_scorer import process_mcq_responses
    result = process_mcq_responses()
    return {"status": "complete", "result": result}

@app.post("/api/v1/pipeline/notify")
async def trigger_notifications():
    from notifications import notify_shortlisted_candidates, notify_rejected_candidates, notify_mcq_passed_candidates, notify_mcq_failed_candidates
    r1 = notify_shortlisted_candidates()
    r2 = notify_rejected_candidates()
    r3 = notify_mcq_passed_candidates()
    r4 = notify_mcq_failed_candidates()
    return {"message": "Notifications complete", "shortlist": r1, "rejection": r2}

@app.post("/api/v1/pipeline/run-all")
async def run_full_pipeline():
    from intake.drive_fetcher import DriveFetcher
    from extraction import process_pending_candidates
    from scoring.pipeline import run_scoring_pipeline
    from notifications import notify_shortlisted_candidates, notify_rejected_candidates, notify_mcq_passed_candidates, notify_mcq_failed_candidates
    fetch   = DriveFetcher().run()
    extract = process_pending_candidates()
    score   = run_scoring_pipeline()
    notify  = notify_shortlisted_candidates()
    notify2 = notify_rejected_candidates()
    return {
        "message": "Full pipeline complete",
        "fetch":   fetch,
        "extract": extract,
        "score":   score,
        "notify_shortlist": notify,
        "notify_rejection": notify2
    }

@app.get("/api/v1/candidates_all")
async def get_all_candidates():
    candidates = list(db_manager.candidates.find({}))
    for c in candidates:
        c["_id"] = str(c["_id"])
    return {"candidates": candidates, "total": len(candidates)}


@app.get("/api/v1/interviews/{candidate_id}")
async def get_interview(candidate_id: str):
    from bson import ObjectId
    interview = db_manager.interviews.find_one({"candidate_id": candidate_id})
    if not interview:
        return {}
    interview["_id"] = str(interview["_id"])
    return interview

@app.post("/api/v1/interviews/{candidate_id}/create")
async def create_interview(candidate_id: str, data: dict):
    from interview import create_interview_session
    interview_id = create_interview_session(candidate_id, data.get("job_id",""))
    return {"interview_id": interview_id} if interview_id else {"error": "Failed"}

@app.post("/api/v1/interviews/{interview_id}/answer")
async def submit_interview_answer(interview_id: str, data: dict):
    from interview import submit_answer
    return submit_answer(interview_id, data["question_number"], data["answer_text"])

@app.post("/api/v1/interviews/{interview_id}/complete")
async def complete_interview_endpoint(interview_id: str):
    from interview import complete_interview
    return complete_interview(interview_id)

@app.get("/api/v1/stats")
async def get_stats():
    return db_manager.get_stats()
"""
Add these two endpoints to ~/recruitment_ai/api/__init__.py

Paste them BEFORE the final line (if __name__ == '__main__': ... or at the end of the file).
"""

# ── Imports to add at the TOP of api/__init__.py if not already there ──────────
# import uuid
# from bson import ObjectId

# ══════════════════════════════════════════════════════════════════════════════
# GET /api/v1/interview/verify/{token}
# Called by interview.html when the page loads.
# Verifies the token, returns candidate name + job title + questions.
# ══════════════════════════════════════════════════════════════════════════════
@app.get("/api/v1/interview/verify/{token}")
def verify_interview_token(token: str):
    """
    Checks whether the interview link token is valid.
    If valid: returns candidate info and interview questions.
    If invalid/used: returns 404.
    """
    from bson import ObjectId
    import ollama as ollama_lib

    # Find the candidate who owns this token
    candidate = db_manager.candidates.find_one({"interview_token": token})
    if not candidate:
        raise HTTPException(status_code=404, detail="Invalid or expired interview link.")

    # Only allow access if candidate is at the right stage
    allowed_statuses = ["mcq_passed", "interviewing"]
    if candidate.get("status") not in allowed_statuses:
        raise HTTPException(
            status_code=400,
            detail="This interview link is no longer active. Please contact HR."
        )

    # Get the job document to build questions
    job = None
    try:
        job = db_manager.jobs.find_one({"_id": ObjectId(candidate.get("job_id", ""))})
    except Exception:
        job = db_manager.jobs.find_one({"_id": candidate.get("job_id", "")})

    job_title  = job.get("title", "the position") if job else "the position"
    job_desc   = job.get("description", "") if job else ""
    skills     = ", ".join(job.get("required_skills", [])) if job else ""

    # If questions were already generated and stored, reuse them
    if candidate.get("interview_questions"):
        questions = candidate["interview_questions"]
    else:
        # Generate 5 questions using the local LLM
        questions = _generate_interview_questions(job_title, job_desc, skills, ollama_lib)
        # Save questions to candidate document so they stay the same on refresh
        db_manager.candidates.update_one(
            {"_id": candidate["_id"]},
            {"$set": {
                "interview_questions": questions,
                "status": "interviewing"
            }}
        )

    return {
        "candidate_name": candidate.get("full_name", "Candidate"),
        "job_title":      job_title,
        "questions":      questions
    }


def _generate_interview_questions(job_title, job_desc, skills, ollama_lib):
    """
    Uses the local Ollama LLM to generate 5 interview questions for the role.
    Returns a list of dicts: [{question, ideal_answer}]
    Falls back to generic questions if LLM fails.
    """
    import json
    from config.settings import settings

    prompt = f"""You are an expert HR interviewer for the role of {job_title}.
Job description: {job_desc[:500]}
Required skills: {skills}

Generate exactly 5 interview questions suitable for this role.
For each question, also provide a brief ideal answer (2-3 sentences) that a strong candidate would give.

Return ONLY valid JSON, no extra text:
[
  {{"question": "...", "ideal_answer": "..."}},
  {{"question": "...", "ideal_answer": "..."}},
  {{"question": "...", "ideal_answer": "..."}},
  {{"question": "...", "ideal_answer": "..."}},
  {{"question": "...", "ideal_answer": "..."}}
]"""

    try:
        response = ollama_lib.chat(
            model=settings.OLLAMA_MODEL,
            messages=[{"role": "user", "content": prompt}],
            options={"temperature": 0.3, "num_predict": 600}
        )
        raw   = response["message"]["content"]
        start = raw.find("[")
        end   = raw.rfind("]") + 1
        data  = json.loads(raw[start:end])
        # Validate structure
        questions = []
        for item in data[:5]:
            if "question" in item and "ideal_answer" in item:
                questions.append({
                    "question":     str(item["question"]).strip(),
                    "ideal_answer": str(item["ideal_answer"]).strip()
                })
        if len(questions) >= 3:
            return questions
    except Exception as e:
        logger.warning(f"LLM question generation failed: {e}. Using fallback questions.")

    # Fallback generic questions if LLM fails
    return [
        {"question": f"Tell me about yourself and why you are interested in the {job_title} role.",
         "ideal_answer": "Candidate describes relevant experience, skills, and motivation clearly."},
        {"question": "What relevant experience or projects have you completed that prepare you for this role?",
         "ideal_answer": "Candidate gives specific examples with technologies or outcomes mentioned."},
        {"question": "Describe a challenging problem you solved and how you approached it.",
         "ideal_answer": "Candidate explains the problem, their thinking process, and the outcome."},
        {"question": "How do you stay up to date with new technologies or developments in your field?",
         "ideal_answer": "Candidate mentions specific resources, communities, or learning habits."},
        {"question": "Where do you see yourself professionally in the next 2-3 years?",
         "ideal_answer": "Candidate shows ambition and alignment with the role and organisation."},
    ]


# ══════════════════════════════════════════════════════════════════════════════
# POST /api/v1/interview/submit/{token}
# Called by interview.html when the candidate clicks "Submit Interview".
# Scores answers, saves to MongoDB + Google Sheet, sends emails.
# ══════════════════════════════════════════════════════════════════════════════
@app.post("/api/v1/interview/submit/{token}")
async def submit_interview(token: str, payload: dict):
    """
    Receives the candidate's answers, scores them with SBERT,
    saves results to MongoDB and Google Sheet, and sends emails.
    """
    from bson import ObjectId
    import datetime

    # Verify the token again
    candidate = db_manager.candidates.find_one({"interview_token": token})
    if not candidate:
        raise HTTPException(status_code=404, detail="Invalid interview token.")

    if candidate.get("status") == "interview_done":
        raise HTTPException(status_code=400, detail="This interview has already been submitted.")

    answers   = payload.get("answers", [])   # [{question, answer}]
    questions = candidate.get("interview_questions", [])

    # ── Score each answer with SBERT ─────────────────────────────────────────
    scores    = []
    transcript = []

    try:
        from sentence_transformers import SentenceTransformer, util
        sbert = SentenceTransformer("all-MiniLM-L6-v2")

        for i, item in enumerate(answers):
            candidate_answer = item.get("answer", "").strip()
            ideal_answer     = questions[i]["ideal_answer"] if i < len(questions) else ""

            if not candidate_answer or not ideal_answer:
                score = 0.0
            else:
                embeddings = sbert.encode([candidate_answer, ideal_answer], convert_to_tensor=True)
                similarity = util.cos_sim(embeddings[0], embeddings[1]).item()
                score = round(max(0.0, min(1.0, similarity)), 4)

            scores.append(score)
            transcript.append({
                "question":       item.get("question", ""),
                "answer":         candidate_answer,
                "score":          score,
                "ideal_answer":   ideal_answer
            })

        overall_score = round((sum(scores) / len(scores)) * 100, 1) if scores else 0.0

    except Exception as e:
        logger.error(f"SBERT scoring failed: {e}")
        overall_score = 0.0
        transcript = [{"question": a.get("question",""), "answer": a.get("answer",""),
                       "score": 0, "ideal_answer": ""} for a in answers]

    # ── Determine pass/fail ──────────────────────────────────────────────────
    from config.settings import settings
    passed     = overall_score >= settings.VOICE_THRESHOLD
    new_status = "interview_done"

    # ── Save to MongoDB ──────────────────────────────────────────────────────
    db_manager.candidates.update_one(
        {"_id": candidate["_id"]},
        {"$set": {
            "status":              new_status,
            "voice_score":         overall_score,
            "voice_passed":        passed,
            "voice_transcript":    transcript,
            "interview_completed_at": datetime.datetime.utcnow(),
            "interview_token":     None   # invalidate the token after use
        }}
    )

    # ── Save interview document ──────────────────────────────────────────────
    db_manager.interviews.insert_one({
        "candidate_id":   str(candidate["_id"]),
        "job_id":         candidate.get("job_id", ""),
        "transcript":     transcript,
        "overall_score":  overall_score,
        "passed":         passed,
        "completed_at":   datetime.datetime.utcnow()
    })

    # ── Update Google Sheet ──────────────────────────────────────────────────
    try:
        from candidate_sheet import update_voice_result
        update_voice_result(candidate.get("email", ""), overall_score, passed)
    except Exception as e:
        logger.warning(f"Google Sheet voice update failed: {e}")

    # ── Send email to candidate ──────────────────────────────────────────────
    try:
        from bson import ObjectId
        job = None
        try:
            job = db_manager.jobs.find_one({"_id": ObjectId(candidate.get("job_id", ""))})
        except Exception:
            job = db_manager.jobs.find_one({"_id": candidate.get("job_id", "")})

        job_title = job.get("title", "the position") if job else "the position"
        name      = candidate.get("full_name", "Candidate")
        email     = candidate.get("email", "")

        if passed:
            subject = f"Your Voice Interview Results for {job_title} — Shortlisted"
            body = (
                f"Dear {name},\n\n"
                f"Thank you for completing the voice interview for the {job_title} position.\n\n"
                f"We are pleased to inform you that you have been shortlisted based on your "
                f"interview performance (score: {overall_score:.0f}/100).\n\n"
                f"Our HR team will be in touch shortly with the next steps.\n\n"
                f"Best regards,\nRecruitment AI - BNU"
            )
        else:
            subject = f"Your Voice Interview Results for {job_title}"
            body = (
                f"Dear {name},\n\n"
                f"Thank you for completing the voice interview for the {job_title} position.\n\n"
                f"After reviewing your interview (score: {overall_score:.0f}/100), we regret to "
                f"inform you that we will not be moving forward with your application at this time.\n\n"
                f"We appreciate your effort and wish you the best in your search.\n\n"
                f"Best regards,\nRecruitment AI - BNU"
            )

        from notifications import send_email, log_notification
        success, error = send_email(email, name, subject, body)
        log_notification(str(candidate["_id"]), candidate.get("job_id",""),
                         email, name, subject, body, "voice_result", success, error)

    except Exception as e:
        logger.warning(f"Candidate result email failed: {e}")

    # ── Send transcript email to HR ───────────────────────────────────────────
    try:
        hr_email = settings.SMTP_SENDER_EMAIL
        hr_name  = "HR Manager"

        transcript_lines = "\n".join([
            f"Q{i+1}: {t['question']}\n"
            f"Answer: {t['answer'] or '(no answer)'}\n"
            f"Score: {round(t['score']*100)}%\n"
            for i, t in enumerate(transcript)
        ])

        hr_subject = f"Interview Transcript — {name} ({job_title}) — Score: {overall_score:.0f}/100"
        hr_body = (
            f"Interview completed by: {name} ({email})\n"
            f"Position: {job_title}\n"
            f"Overall Score: {overall_score:.0f}/100\n"
            f"Decision: {'PASSED' if passed else 'DID NOT PASS'}\n\n"
            f"{'='*50}\n"
            f"TRANSCRIPT\n"
            f"{'='*50}\n\n"
            f"{transcript_lines}"
            f"\n{'='*50}\n"
            f"This email was generated automatically by Recruitment AI."
        )

        from notifications import send_email
        send_email(hr_email, hr_name, hr_subject, hr_body)
        logger.success(f"HR transcript email sent for {name}")

    except Exception as e:
        logger.warning(f"HR transcript email failed: {e}")

    logger.success(f"Interview submitted: {name} — {overall_score:.1f}/100 — {'PASSED' if passed else 'FAILED'}")

    return {
        "status":        "submitted",
        "overall_score": overall_score,
        "passed":        passed
    }
