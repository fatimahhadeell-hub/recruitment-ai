import uuid
import smtplib
import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional
from loguru import logger
from config.settings import settings
from database.mongodb import db_manager
from models.schemas import NotificationDocument, NotificationStatus


def build_shortlist_email(candidate_name, job_title, mcq_form_url=None, mcq_deadline_days=3):
    subject = f"Your Application for {job_title} - Next Steps"
    if mcq_form_url:
        body = (
            f"Dear {candidate_name},\n\n"
            f"Thank you for applying for the {job_title} position.\n\n"
            f"We are pleased to inform you that you have been shortlisted based on your CV.\n\n"
            f"The next stage is an online assessment test. Please complete it within {mcq_deadline_days} days.\n\n"
            f"Assessment Link: {mcq_form_url}\n\n"
            f"Please use the same email address you applied with when submitting the test.\n\n"
            f"Best regards,\nRecruitment AI - BNU"
        )
    else:
        body = (
            f"Dear {candidate_name},\n\n"
            f"Thank you for applying for the {job_title} position.\n\n"
            f"We are pleased to inform you that you have been shortlisted for the next stage.\n\n"
            f"Our team will be in touch shortly with further details.\n\n"
            f"Best regards,\nRecruitment AI - BNU"
        )
    return subject, body


def build_mcq_result_email(candidate_name, job_title, passed, mcq_score):
    """Email sent after MCQ test is evaluated — shortlist or decline."""
    if passed:
        subject = f"Your Assessment Results for {job_title} - Congratulations"
        body = (
            f"Dear {candidate_name},\n\n"
            f"Thank you for completing the online assessment for the {job_title} position.\n\n"
            f"We are pleased to inform you that you have passed the assessment with a score of "
            f"{mcq_score:.0f}/100.\n\n"
            f"You have been shortlisted for the next stage: a voice interview conducted by our AI system.\n\n"
            f"Our team will be in touch shortly with instructions on how to complete the voice interview.\n\n"
            f"Best regards,\nRecruitment AI - BNU"
        )
    else:
        subject = f"Your Assessment Results for {job_title}"
        body = (
            f"Dear {candidate_name},\n\n"
            f"Thank you for completing the online assessment for the {job_title} position.\n\n"
            f"After reviewing your assessment results (score: {mcq_score:.0f}/100), "
            f"we regret to inform you that we will not be moving forward with your application at this time.\n\n"
            f"We appreciate your interest and encourage you to apply for future opportunities.\n\n"
            f"Best regards,\nRecruitment AI - BNU"
        )
    return subject, body


def build_voice_invite_email(candidate_name, job_title, interview_url=None):
    """Email inviting an MCQ-passed candidate to complete the voice interview."""
    subject = f"Voice Interview Invitation for {job_title}"
    if interview_url:
        body = (
            f"Dear {candidate_name},\n\n"
            f"Congratulations on passing the assessment test for the {job_title} position.\n\n"
            f"You have been invited to complete a voice interview as the next stage of our selection process.\n\n"
            f"Please click the link below to start your interview. The interview is conducted by our AI system. "
            f"You will be asked 5 role-relevant questions and should speak your answers clearly into your microphone.\n\n"
            f"Your interview link (unique to you — do not share):\n"
            f"{interview_url}\n\n"
            f"Requirements:\n"
            f"- Use Google Chrome or Microsoft Edge (Safari does not support voice recording)\n"
            f"- Find a quiet place with no background noise\n"
            f"- Allow microphone access when prompted\n\n"
            f"Best regards,\nRecruitment AI - BNU"
        )
    else:
        body = (
            f"Dear {candidate_name},\n\n"
            f"Congratulations on passing the assessment test for the {job_title} position.\n\n"
            f"You have been invited to complete a voice interview. Our HR team will be in touch with further details.\n\n"
            f"Best regards,\nRecruitment AI - BNU"
        )
    return subject, body


def build_rejection_email(candidate_name, job_title):
    subject = f"Your Application for {job_title}"
    body = (
        f"Dear {candidate_name},\n\n"
        f"Thank you for applying for the {job_title} position.\n\n"
        f"After carefully reviewing your application, we regret to inform you that we will not be "
        f"moving forward with your application at this time.\n\n"
        f"We appreciate your interest and encourage you to apply for future opportunities.\n\n"
        f"Best regards,\nThe Recruitment Team"
    )
    return subject, body


def send_email(recipient_email, recipient_name, subject, body):
    if not settings.SMTP_ENABLED:
        logger.info(f"[EMAIL LOGGED] To: {recipient_name} <{recipient_email}> Subject: {subject}")
        return True, None
    try:
        msg = MIMEMultipart()
        msg["From"]    = f"{settings.SMTP_SENDER_NAME} <{settings.SMTP_SENDER_EMAIL}>"
        msg["To"]      = recipient_email
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            if settings.SMTP_USERNAME:
                server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
            server.sendmail(settings.SMTP_SENDER_EMAIL, recipient_email, msg.as_string())
        logger.success(f"Email sent to {recipient_name} <{recipient_email}>")
        return True, None
    except Exception as e:
        logger.error(f"Email failed: {e}")
        return False, str(e)


def log_notification(candidate_id, job_id, recipient_email, recipient_name,
                     subject, body, notification_type, success, error_message=None):
    status = NotificationStatus.SENT if success else NotificationStatus.FAILED
    if not settings.SMTP_ENABLED:
        status = NotificationStatus.SKIPPED
    doc = NotificationDocument(
        candidate_id=candidate_id, job_id=job_id,
        recipient_email=recipient_email, recipient_name=recipient_name,
        subject=subject, body_text=body, notification_type=notification_type,
        status=status, error_message=error_message,
        sent_at=datetime.datetime.utcnow() if success else None
    )
    db_manager.notifications.insert_one(
        doc.model_dump(by_alias=True, exclude_none=True)
    )


def _get_job(job_id):
    """Helper to fetch a job document by ID, handling both ObjectId and string."""
    from bson import ObjectId
    try:
        return db_manager.jobs.find_one({"_id": ObjectId(job_id)})
    except Exception:
        return db_manager.jobs.find_one({"_id": job_id})


def notify_shortlisted_candidates():
    """
    Sends the MCQ test link email to candidates with status 'shortlisted'.

    Race condition fix: also checks candidates who jumped directly to 'mcq_passed'
    without ever receiving a shortlist notification. For those candidates, sends
    a voice interview invitation instead (since they already completed the MCQ).
    """
    result = {"sent": 0, "skipped": 0, "failed": 0}

    # ── Part 1: candidates still at 'shortlisted' status ─────────────────────
    shortlisted = list(db_manager.candidates.find({"status": "shortlisted"}))
    logger.info(f"Notification check: {len(shortlisted)} shortlisted candidates.")

    for candidate in shortlisted:
        candidate_id = str(candidate["_id"])
        email  = candidate.get("email", "")
        name   = candidate.get("full_name", "Candidate")
        job_id = candidate.get("job_id", "")
        if not email:
            result["skipped"] += 1
            continue
        # Skip if shortlist email already sent
        if db_manager.notifications.find_one(
                {"candidate_id": candidate_id, "notification_type": "shortlist"}):
            result["skipped"] += 1
            continue
        job       = _get_job(job_id)
        job_title = job.get("title", "the position") if job else "the position"
        mcq_url   = job.get("mcq_form_url") if job else None
        mcq_days  = job.get("mcq_deadline_days", 3) if job else 3
        subject, body = build_shortlist_email(name, job_title, mcq_url, mcq_days)
        success, error = send_email(email, name, subject, body)
        log_notification(candidate_id, job_id, email, name,
                         subject, body, "shortlist", success, error)
        if success:
            result["sent"] += 1
            logger.success(f"Shortlist notification sent to {name}")
        else:
            result["failed"] += 1

    # ── Part 2: race condition fix ────────────────────────────────────────────
    # Candidates who jumped to 'mcq_passed' before the shortlist email could fire.
    # They never got any email. Send them the voice interview invitation.
    mcq_passed = list(db_manager.candidates.find({"status": "mcq_passed"}))
    for candidate in mcq_passed:
        candidate_id = str(candidate["_id"])
        email  = candidate.get("email", "")
        name   = candidate.get("full_name", "Candidate")
        job_id = candidate.get("job_id", "")
        if not email:
            continue
        # Only act if they have never received ANY notification
        already_notified = db_manager.notifications.find_one(
            {"candidate_id": candidate_id,
             "notification_type": {"$in": ["shortlist", "mcq_result", "voice_invite"]}}
        )
        if already_notified:
            continue
        job       = _get_job(job_id)
        job_title = job.get("title", "the position") if job else "the position"
        token = candidate.get("interview_token")
        if not token:
            token = str(uuid.uuid4())
            db_manager.candidates.update_one(
                {"_id": candidate["_id"]},
                {"$set": {"interview_token": token}}
            )
        server_ip     = getattr(settings, "SERVER_IP", "192.168.18.14")
        interview_url = f"http://{server_ip}:8080/interview.html?token={token}"
        subject, body = build_voice_invite_email(name, job_title, interview_url)
        success, error = send_email(email, name, subject, body)
        log_notification(candidate_id, job_id, email, name,
                         subject, body, "voice_invite", success, error)
        if success:
            result["sent"] += 1
            logger.success(f"Voice invite sent to {name} (race condition catch-up): {interview_url}")
        else:
            result["failed"] += 1

    logger.info(f"Notifications done: {result}")
    return result


def notify_mcq_passed_candidates():
    """
    Sends voice interview invitation emails to candidates who passed the MCQ test.
    Generates a unique interview token per candidate and includes the link in the email.
    Skips candidates who have already received a voice_invite notification.
    Called by the background pipeline after MCQ evaluation runs.
    """
    result = {"sent": 0, "skipped": 0, "failed": 0}
    passed = list(db_manager.candidates.find({"status": "mcq_passed"}))
    logger.info(f"MCQ passed notification check: {len(passed)} candidates.")

    # Get the server IP from settings, fallback to localhost
    server_ip = getattr(settings, 'SERVER_IP', '192.168.18.14')
    base_url  = f"http://{server_ip}:8080"

    for candidate in passed:
        candidate_id = str(candidate["_id"])
        email  = candidate.get("email", "")
        name   = candidate.get("full_name", "Candidate")
        job_id = candidate.get("job_id", "")
        if not email:
            result["skipped"] += 1
            continue
        # Skip if voice invite already sent
        if db_manager.notifications.find_one(
                {"candidate_id": candidate_id, "notification_type": "voice_invite"}):
            result["skipped"] += 1
            continue

        # Generate a unique token for this candidate if they don't have one yet
        token = candidate.get("interview_token")
        if not token:
            token = str(uuid.uuid4())
            db_manager.candidates.update_one(
                {"_id": candidate["_id"]},
                {"$set": {"interview_token": token}}
            )

        interview_url = f"{base_url}/interview.html?token={token}"
        job       = _get_job(job_id)
        job_title = job.get("title", "the position") if job else "the position"
        subject, body = build_voice_invite_email(name, job_title, interview_url)
        success, error = send_email(email, name, subject, body)
        log_notification(candidate_id, job_id, email, name,
                         subject, body, "voice_invite", success, error)
        if success:
            result["sent"] += 1
            logger.success(f"Voice interview invitation sent to {name}: {interview_url}")
        else:
            result["failed"] += 1

    logger.info(f"MCQ passed notifications done: {result}")
    return result


def notify_mcq_failed_candidates():
    """
    Sends decline emails to candidates who failed the MCQ test (status: not_selected
    after MCQ stage). Only sends if they have not already received any rejection email.
    """
    result = {"sent": 0, "skipped": 0, "failed": 0}
    # Find candidates declined at MCQ stage: not_selected AND has an mcq_score
    declined = list(db_manager.candidates.find({
        "status": "not_selected",
        "mcq_score": {"$ne": None}
    }))

    for candidate in declined:
        candidate_id = str(candidate["_id"])
        email  = candidate.get("email", "")
        name   = candidate.get("full_name", "Candidate")
        job_id = candidate.get("job_id", "")
        if not email:
            result["skipped"] += 1
            continue
        if db_manager.notifications.find_one(
                {"candidate_id": candidate_id,
                 "notification_type": {"$in": ["rejection", "mcq_result"]}}):
            result["skipped"] += 1
            continue
        job       = _get_job(job_id)
        job_title = job.get("title", "the position") if job else "the position"
        mcq_score = candidate.get("mcq_score", 0)
        subject, body = build_mcq_result_email(name, job_title, False, mcq_score)
        success, error = send_email(email, name, subject, body)
        log_notification(candidate_id, job_id, email, name,
                         subject, body, "mcq_result", success, error)
        if success:
            result["sent"] += 1
        else:
            result["failed"] += 1

    logger.info(f"MCQ failed notifications done: {result}")
    return result


def notify_rejected_candidates():
    """
    Sends decline emails to candidates rejected at CV stage (status: not_selected,
    no mcq_score). Skips if a rejection email was already sent.
    """
    result = {"sent": 0, "skipped": 0, "failed": 0}
    # Only CV-stage rejections (no mcq_score means rejected before MCQ)
    rejected = list(db_manager.candidates.find({
        "status": "not_selected",
        "mcq_score": None
    }))
    logger.info(f"Rejection check: {len(rejected)} rejected candidates.")

    for candidate in rejected:
        candidate_id = str(candidate["_id"])
        email  = candidate.get("email", "")
        name   = candidate.get("full_name", "Candidate")
        job_id = candidate.get("job_id", "")
        if not email:
            result["skipped"] += 1
            continue
        if db_manager.notifications.find_one(
                {"candidate_id": candidate_id, "notification_type": "rejection"}):
            result["skipped"] += 1
            continue
        job       = _get_job(job_id)
        job_title = job.get("title", "the position") if job else "the position"
        subject, body = build_rejection_email(name, job_title)
        success, error = send_email(email, name, subject, body)
        log_notification(candidate_id, job_id, email, name,
                         subject, body, "rejection", success, error)
        if success:
            result["sent"] += 1
        else:
            result["failed"] += 1

    logger.info(f"Rejection notifications done: {result}")
    return result
