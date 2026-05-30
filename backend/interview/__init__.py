
import datetime
from typing import List, Optional
from loguru import logger
from sentence_transformers import SentenceTransformer, util
import ollama
from config.settings import settings
from database.mongodb import db_manager
from models.schemas import InterviewDocument, InterviewQuestion, CandidateStatus

# Load SBERT model once at module level so it is not reloaded on every call
logger.info("Loading SBERT model for interview scoring...")
_sbert_model = None

def get_sbert_model():
    global _sbert_model
    if _sbert_model is None:
        _sbert_model = SentenceTransformer(settings.SBERT_MODEL)
        logger.success(f"SBERT model loaded: {settings.SBERT_MODEL}")
    return _sbert_model

def generate_interview_questions(job: dict, cv_text: str, num_questions: int = 5) -> List[dict]:
    prompt = (
        f"You are an expert interviewer. Generate {num_questions} interview questions "
        f"for this job and candidate.\n\n"
        f"JOB TITLE: {job.get('title','')}\n"
        f"JOB DESCRIPTION: {job.get('description','')[:300]}\n"
        f"REQUIRED SKILLS: {', '.join(job.get('required_skills',[]))}\n\n"
        f"CANDIDATE CV SUMMARY:\n{cv_text[:1000]}\n\n"
        f"Generate exactly {num_questions} questions. For each question also provide "
        f"a model answer (what a strong candidate would say). "
        f"Return ONLY valid JSON as a list:\n"
        f'[{{"question":"...","ideal_answer":"..."}}]'
    )
    try:
        response = ollama.chat(
            model=settings.OLLAMA_MODEL,
            messages=[{"role":"user","content":prompt}],
            options={"temperature":0.3,"num_predict":1000}
        )
        raw = response["message"]["content"].strip()
        # Extract JSON array
        start = raw.find("[")
        end   = raw.rfind("]") + 1
        if start == -1 or end == 0:
            raise ValueError("No JSON array found")
        import json
        questions = json.loads(raw[start:end])
        logger.success(f"Generated {len(questions)} interview questions")
        return questions
    except Exception as e:
        logger.error(f"Failed to generate questions: {e}")
        # Return fallback generic questions
        return [
            {"question": "Tell me about yourself and your relevant experience.", "ideal_answer": "A strong answer covers education, experience, skills and motivation relevant to the role."},
            {"question": "Why are you interested in this role?", "ideal_answer": "A strong answer shows research into the company and clear alignment with career goals."},
            {"question": "Describe a challenging project you worked on.", "ideal_answer": "A strong answer uses the STAR method: Situation, Task, Action, Result."},
            {"question": "What are your strongest technical skills relevant to this position?", "ideal_answer": "A strong answer lists specific skills with concrete examples of their application."},
            {"question": "Where do you see yourself in 3 years?", "ideal_answer": "A strong answer shows ambition, realistic planning, and alignment with the role."},
        ]

def score_answer(candidate_answer: str, ideal_answer: str) -> float:
    if not candidate_answer or not candidate_answer.strip():
        return 0.0
    model = get_sbert_model()
    embeddings = model.encode([candidate_answer, ideal_answer], convert_to_tensor=True)
    similarity = util.cos_sim(embeddings[0], embeddings[1]).item()
    return round(max(0.0, min(1.0, similarity)), 4)

def create_interview_session(candidate_id: str, job_id: str) -> Optional[str]:
    candidate = db_manager.candidates.find_one({"_id": candidate_id}) or                 db_manager.candidates.find_one({"_id": __import__("bson").ObjectId(candidate_id)})
    if not candidate:
        logger.error(f"Candidate not found: {candidate_id}")
        return None
    cv_text = candidate.get("raw_cv_text","")
    try:
        from bson import ObjectId
        job = db_manager.jobs.find_one({"_id": ObjectId(job_id)})
    except Exception:
        job = db_manager.jobs.find_one({"_id": job_id})
    if not job:
        logger.error(f"Job not found: {job_id}")
        return None
    existing = db_manager.interviews.find_one({"candidate_id": candidate_id, "job_id": job_id})
    if existing:
        logger.info(f"Interview already exists for candidate {candidate_id}")
        return str(existing["_id"])
    logger.info(f"Generating interview questions for {candidate.get('full_name','?')}...")
    raw_questions = generate_interview_questions(job, cv_text, num_questions=5)
    questions = [
        InterviewQuestion(
            question_number=i+1,
            question_text=q.get("question",""),
            ideal_answer=q.get("ideal_answer","")
        )
        for i, q in enumerate(raw_questions)
    ]
    interview = InterviewDocument(
        candidate_id=candidate_id,
        job_id=job_id,
        status="pending",
        questions=questions
    )
    doc    = interview.model_dump(by_alias=True, exclude_none=True)
    result = db_manager.interviews.insert_one(doc)
    db_manager.candidates.update_one(
        {"_id": __import__("bson").ObjectId(candidate_id)},
        {"$set": {"status": CandidateStatus.INTERVIEWING.value, "updated_at": datetime.datetime.utcnow()}}
    )
    logger.success(f"Interview session created: {result.inserted_id}")
    return str(result.inserted_id)

def submit_answer(interview_id: str, question_number: int, answer_text: str) -> dict:
    from bson import ObjectId
    interview = db_manager.interviews.find_one({"_id": ObjectId(interview_id)})
    if not interview:
        return {"error": "Interview not found"}
    questions = interview.get("questions", [])
    target    = next((q for q in questions if q.get("question_number") == question_number), None)
    if not target:
        return {"error": f"Question {question_number} not found"}
    ideal          = target.get("ideal_answer","")
    similarity     = score_answer(answer_text, ideal)
    llm_feedback   = f"Similarity score: {similarity:.2f}. " + (
        "Strong answer." if similarity > 0.6 else
        "Partially relevant." if similarity > 0.3 else
        "Consider elaborating more."
    )
    db_manager.interviews.update_one(
        {"_id": ObjectId(interview_id), "questions.question_number": question_number},
        {"$set": {
            "questions.$.answer_text":     answer_text,
            "questions.$.similarity_score":similarity,
            "questions.$.llm_feedback":    llm_feedback,
            "updated_at":                  datetime.datetime.utcnow()
        }}
    )
    return {"question_number": question_number, "similarity_score": similarity, "feedback": llm_feedback}

def complete_interview(interview_id: str) -> dict:
    from bson import ObjectId
    interview = db_manager.interviews.find_one({"_id": ObjectId(interview_id)})
    if not interview:
        return {"error": "Interview not found"}
    questions = interview.get("questions",[])
    scores    = [q.get("similarity_score",0) for q in questions if q.get("similarity_score") is not None]
    overall   = round((sum(scores)/len(scores))*100, 2) if scores else 0.0
    db_manager.interviews.update_one(
        {"_id": ObjectId(interview_id)},
        {"$set": {
            "status":                  "completed",
            "overall_interview_score": overall,
            "completed_at":            datetime.datetime.utcnow(),
            "updated_at":              datetime.datetime.utcnow()
        }}
    )
    candidate_id = interview.get("candidate_id","")
    try:
        db_manager.candidates.update_one(
            {"_id": ObjectId(candidate_id)},
            {"$set": {"status": CandidateStatus.INTERVIEW_DONE.value, "updated_at": datetime.datetime.utcnow()}}
        )
    except Exception:
        pass
    logger.success(f"Interview completed. Overall score: {overall}/100")
    return {"interview_id": interview_id, "overall_score": overall, "questions_scored": len(scores)}
