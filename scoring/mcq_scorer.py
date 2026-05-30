try:
    from candidate_sheet import update_mcq_result
    SHEET_ENABLED = True
except Exception:
    SHEET_ENABLED = False

import json
import datetime
from loguru import logger
from config.settings import settings
from database.mongodb import db_manager
import ollama

# Any status that means the candidate passed the CV stage and is eligible for MCQ
CV_PASSED_STATUSES = ['shortlisted', 'mcq_passed', 'interviewing', 'interview_done', 'interview_complete']

def score_mcq_response(response_row, job):
    """
    Evaluates a candidate's MCQ test responses against correct answers.
    response_row: dict of question -> selected answer from Google Sheets
    job: the job document from Atlas containing correct answers
    Returns: (score out of 100, breakdown list)
    """
    correct_answers = job.get('mcq_correct_answers', {})
    if not correct_answers:
        logger.warning("No correct answers stored in job. Cannot score MCQ.")
        return 0.0, []

    total_questions = len(correct_answers)
    correct_count   = 0
    breakdown       = []

    for question, correct_answer in correct_answers.items():
        candidate_answer = response_row.get(question, '').strip()
        is_correct = candidate_answer.lower() == correct_answer.lower()
        if is_correct:
            correct_count += 1
        breakdown.append({
            'question':         question[:60],
            'correct_answer':   correct_answer,
            'candidate_answer': candidate_answer,
            'is_correct':       is_correct,
        })
        logger.debug(f"Q: {question[:40]} | Correct: {correct_answer} | Got: {candidate_answer} | {'PASS' if is_correct else 'FAIL'}")

    score = round((correct_count / total_questions) * 100, 1) if total_questions > 0 else 0.0
    logger.success(f"MCQ Score: {score}/100 ({correct_count}/{total_questions} correct)")
    return score, breakdown


def process_mcq_responses():
    """
    Reads MCQ responses from Google Sheets and scores each one.
    Called manually or by the MCQ poller.
    Returns summary dict.
    """
    from intake.google_auth import get_authorized_session
    import urllib.parse

    result = {'processed': 0, 'skipped': 0, 'errors': 0}

    # Get all active jobs with MCQ sheets configured
    jobs = list(db_manager.jobs.find({
        'status': 'active',
        'mcq_sheets_id': {'$exists': True, '$ne': ''}
    }))

    for job in jobs:
        mcq_sheet_id = job.get('mcq_sheets_id', '')
        if not mcq_sheet_id:
            continue

        logger.info(f"Checking MCQ responses for job: {job['title']}")

        # Read MCQ response sheet
        try:
            session     = get_authorized_session()
            range_param = urllib.parse.quote('Form responses 1!A:Z')
            url         = f'https://sheets.googleapis.com/v4/spreadsheets/{mcq_sheet_id}/values/{range_param}'
            response    = session.get(url)

            if response.status_code != 200:
                logger.error(f"Could not read MCQ sheet: {response.status_code}")
                continue

            values = response.json().get('values', [])
            if len(values) < 2:
                logger.info("No MCQ responses yet.")
                continue

            headers   = values[0]
            data_rows = values[1:]
            rows      = [dict(zip(headers, row + [''] * (len(headers) - len(row)))) for row in data_rows]

        except Exception as e:
            logger.error(f"Error reading MCQ sheet: {e}")
            result['errors'] += 1
            continue

        for row in rows:
            email     = (row.get('Email Address') or row.get('Email') or row.get('email') or row.get('Email address') or '').strip()
            full_name = (row.get('Full Name') or row.get('Name') or row.get('full_name') or '').strip()

            if not email:
                result['skipped'] += 1
                continue

            candidate = None

            # Match by full name + email + job (most specific)
            if full_name:
                candidate = db_manager.candidates.find_one({
                    'email':    email,
                    'full_name': full_name,
                    'status':   {'$in': CV_PASSED_STATUSES},
                    'job_id':   str(job['_id'])
                })

            # Fallback: full name + email without job filter
            if not candidate and full_name:
                candidate = db_manager.candidates.find_one({
                    'email':    email,
                    'full_name': full_name,
                    'status':   {'$in': CV_PASSED_STATUSES}
                })

            # Last resort: email + job only
            if not candidate:
                candidate = db_manager.candidates.find_one({
                    'email':  email,
                    'status': {'$in': CV_PASSED_STATUSES},
                    'job_id': str(job['_id'])
                })

            # Last last resort: email only, any CV-passed status
            if not candidate:
                candidate = db_manager.candidates.find_one({
                    'email':  email,
                    'status': {'$in': CV_PASSED_STATUSES}
                })

            if not candidate:
                logger.warning(f"No shortlisted candidate found for: {full_name} <{email}>")
                result['skipped'] += 1
                continue

            # Skip if already scored
            if candidate.get('mcq_score') is not None:
                logger.debug(f"Already scored: {candidate.get('full_name')} - skipping")
                result['skipped'] += 1
                continue

            # Score the MCQ
            try:
                score, breakdown = score_mcq_response(row, job)
                threshold  = job.get('mcq_threshold', settings.MCQ_THRESHOLD)
                passed     = score >= threshold
                new_status = 'mcq_passed' if passed else 'not_selected'

                db_manager.candidates.update_one(
                    {'_id': candidate['_id']},
                    {'$set': {
                        'mcq_score':     score,
                        'mcq_breakdown': breakdown,
                        'mcq_passed':    passed,
                        'status':        new_status,
                        'updated_at':    datetime.datetime.utcnow()
                    }}
                )
                logger.success(f"MCQ scored: {candidate['full_name']} - {score}/100 - {'PASSED' if passed else 'FAILED'}")

                if SHEET_ENABLED:
                    try:
                        update_mcq_result(candidate.get('email', ''), score, passed)
                    except Exception as e:
                        logger.warning(f"MCQ sheet update failed: {e}")

                result['processed'] += 1

            except Exception as e:
                logger.error(f"Error scoring MCQ for {email}: {e}")
                result['errors'] += 1

    logger.info(f"MCQ processing complete: {result}")
    return result
