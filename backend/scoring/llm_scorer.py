
import json
import time
import re
from typing import Optional
import ollama
from loguru import logger
from config.settings import settings
from models.schemas import ParameterScore, ScoreDocument, ScoringWeights
from scoring.tenure_calculator import calculate_stability_score

PROMPT = (
    "You are an expert HR recruiter. Score this candidate CV against the job.\n\n"
    "JOB TITLE: {job_title}\n"
    "JOB DESCRIPTION: {job_description}\n"
    "REQUIRED SKILLS: {required_skills}\n"
    "REQUIRED EDUCATION: {required_education}\n"
    "VALUES: {values_prompt}\n\n"
    "CANDIDATE CV:\n{cv_text}\n\n"
    "Score each parameter 0-10. Keep justifications under 20 words each.\n"
    "Return ONLY this JSON, no other text:\n"
    '{{"education":{{"score":0,"justification":""}},'
    '"experience":{{"score":0,"justification":""}},'
    '"skills":{{"score":0,"justification":""}},'
    '"progression":{{"score":0,"justification":""}},'
    '"values":{{"score":0,"justification":""}},'
    '"communication":{{"score":0,"justification":""}}}}'
)

def extract_json(text):
    start = text.find("{")
    end   = text.rfind("}") + 1
    if start == -1 or end == 0:
        return None
    candidate = text[start:end]
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        pass
    # Fix truncated JSON by closing open braces
    try:
        open_braces = candidate.count("{") - candidate.count("}")
        fixed = candidate + "}" * open_braces
        return json.loads(fixed)
    except Exception:
        pass
    # Extract only complete fields using regex
    try:
        fields = re.findall(r'"(\w+)":\s*\{\s*"score":\s*(\d+(?:\.\d+)?),\s*"justification":\s*"([^"]*)"\s*\}', candidate)
        if fields:
            return {name: {"score": float(score), "justification": just} for name, score, just in fields}
    except Exception:
        pass
    return None

def score_candidate_with_llm(cv_text, job, weights, work_experience):
    start_time = time.time()
    model = settings.OLLAMA_MODEL
    prompt = PROMPT.format(
        job_title=job.get("title",""),
        job_description=job.get("description","")[:300],
        required_skills=", ".join(job.get("required_skills",[])),
        required_education=job.get("required_education",""),
        values_prompt=job.get("values_prompt",""),
        cv_text=cv_text[:1500]
    )
    logger.info(f"Sending CV to LLM ({model}) for scoring...")
    try:
        response = ollama.chat(
            model=model,
            messages=[{"role":"user","content":prompt}],
            options={
    "temperature": 0.1,
    "num_predict": 400,
    "num_ctx": 2048,
}
        )
        raw = response["message"]["content"].strip()
        logger.debug(f"LLM response: {raw[:300]}")
    except Exception as e:
        logger.error(f"LLM call failed: {e}")
        return None

    scores_data = extract_json(raw)
    if not scores_data:
        logger.error(f"Could not extract valid JSON from LLM response: {raw[:200]}")
        return None

    stability_score, stability_justification = calculate_stability_score(work_experience)

    def make_param(key, weight):
        data  = scores_data.get(key, {"score":5.0,"justification":"Not evaluated."})
        score = max(0.0, min(10.0, float(data.get("score", 5.0))))
        return ParameterScore(
            score=score,
            justification=data.get("justification",""),
            weighted_contribution=round((score/10.0)*weight*100, 2)
        )

    ep   = make_param("education",     weights.education)
    exp  = make_param("experience",    weights.experience)
    sp   = make_param("skills",        weights.skills)
    pp   = make_param("progression",   weights.progression)
    vp   = make_param("values",        weights.values)
    cp   = make_param("communication", weights.communication)
    stab = ParameterScore(
        score=stability_score,
        justification=stability_justification,
        weighted_contribution=round((stability_score/10.0)*weights.stability*100, 2)
    )

    final_score = round(min(100.0,
        ep.weighted_contribution + exp.weighted_contribution +
        sp.weighted_contribution + stab.weighted_contribution +
        pp.weighted_contribution + vp.weighted_contribution +
        cp.weighted_contribution
    ), 2)

    duration = round(time.time()-start_time, 1)
    logger.success(f"Score: {final_score}/100 in {duration}s")

    return ScoreDocument(
        candidate_id="", job_id="",
        education=ep, experience=exp, skills=sp,
        stability=stab, progression=pp, values=vp, communication=cp,
        final_score=final_score, is_shortlisted=False,
        weights_used={
            "education":weights.education,"experience":weights.experience,
            "skills":weights.skills,"stability":weights.stability,
            "progression":weights.progression,"values":weights.values,
            "communication":weights.communication
        },
        llm_model_used=model, scoring_duration_seconds=duration
    )
