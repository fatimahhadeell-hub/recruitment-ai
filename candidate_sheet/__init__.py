import urllib.parse
import datetime
from loguru import logger
from config.settings import settings

SHEET_ID = '1ZmGylr3C2wDX2iMWQsi1YAW22s7XvOe842N3h0nR3Cs'

HEADERS = [
    'Timestamp', 'Full Name', 'Email', 'Phone',
    'Education', 'Experience', 'Skills',
    'CV Score', 'CV Decision',
    'MCQ Score', 'MCQ Decision',
    'Voice Score', 'Voice Decision',
    'Final Status', 'Job Title'
]

def get_write_session():
    from google.oauth2 import service_account
    import google.auth.transport.requests
    creds = service_account.Credentials.from_service_account_file(
        settings.GOOGLE_CREDENTIALS_FILE,
        scopes=['https://www.googleapis.com/auth/spreadsheets']
    )
    auth_req = google.auth.transport.requests.Request()
    creds.refresh(auth_req)
    return google.auth.transport.requests.AuthorizedSession(creds)

def _ensure_headers(session):
    """Write header row if sheet is empty."""
    range_param = urllib.parse.quote('Sheet1!A1:O1')
    url = f'https://sheets.googleapis.com/v4/spreadsheets/{SHEET_ID}/values/{range_param}'
    resp = session.get(url)
    existing = resp.json().get('values', [])
    if not existing or existing[0][0] != 'Timestamp':
        session.put(
            url + '?valueInputOption=RAW',
            json={'values': [HEADERS]}
        )
        logger.info("Sheet headers written.")

def _get_all_rows(session):
    """Returns all rows as list of lists. Row 0 = headers."""
    range_param = urllib.parse.quote('Sheet1!A:O')
    url = f'https://sheets.googleapis.com/v4/spreadsheets/{SHEET_ID}/values/{range_param}'
    resp = session.get(url)
    return resp.json().get('values', [])

def _find_row_by_email(session, email):
    """Returns 1-based row number of candidate, skipping header row. Returns None if not found."""
    rows = _get_all_rows(session)
    for i, row in enumerate(rows):
        if i == 0:
            continue  # skip header row
        if len(row) > 2 and row[2].strip().lower() == email.strip().lower():
            return i + 1  # 1-based
    return None

def _update_cell(session, row_num, col_letter, value):
    range_param = urllib.parse.quote(f'Sheet1!{col_letter}{row_num}')
    url = f'https://sheets.googleapis.com/v4/spreadsheets/{SHEET_ID}/values/{range_param}?valueInputOption=RAW'
    session.put(url, json={'values': [[str(value) if value is not None else '']]})

def _append_row(session, values):
    range_param = urllib.parse.quote('Sheet1!A:O')
    url = f'https://sheets.googleapis.com/v4/spreadsheets/{SHEET_ID}/values/{range_param}:append?valueInputOption=RAW&insertDataOption=INSERT_ROWS'
    response = session.post(url, json={'values': [values]})
    return response.status_code == 200

def add_candidate(candidate, job_title=''):
    """
    Adds a new candidate row. If candidate already exists (matched by email),
    skips to avoid duplicates. Safe to call multiple times.
    """
    try:
        session = get_write_session()
        _ensure_headers(session)
        email = candidate.get('email', '')
        existing_row = _find_row_by_email(session, email)
        if existing_row:
            logger.info(f"Candidate {email} already in sheet at row {existing_row}, skipping add.")
            return True
        values = [
            datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M'),
            candidate.get('full_name', ''),
            email,
            candidate.get('phone', ''),
            '', '', '',         # Education, Experience, Skills
            '', 'Pending',      # CV Score, CV Decision
            '', 'Pending',      # MCQ Score, MCQ Decision
            '', 'Pending',      # Voice Score, Voice Decision
            'Applied',          # Final Status
            job_title,          # Job Title
        ]
        success = _append_row(session, values)
        if success:
            logger.success(f"Candidate {candidate.get('full_name', email)} added to sheet.")
        return success
    except Exception as e:
        logger.error(f"Failed to add candidate to sheet: {e}")
        return False

def update_cv_result(email, cv_score, shortlisted, education='', experience='', skills='', full_name='', job_title=''):
    """Updates CV scoring columns. If candidate row missing, creates it first."""
    try:
        session = get_write_session()
        _ensure_headers(session)
        row_num = _find_row_by_email(session, email)
        if not row_num:
            logger.warning(f"Candidate {email} not in sheet — adding now.")
            add_candidate({'full_name': full_name, 'email': email}, job_title)
            row_num = _find_row_by_email(session, email)
        if not row_num:
            logger.error(f"Still cannot find row for {email} after adding.")
            return False
        _update_cell(session, row_num, 'E', education)
        _update_cell(session, row_num, 'F', experience)
        _update_cell(session, row_num, 'G', skills)
        _update_cell(session, row_num, 'H', round(cv_score, 1) if cv_score is not None else '')
        _update_cell(session, row_num, 'I', 'Shortlisted' if shortlisted else 'Not Selected')
        _update_cell(session, row_num, 'N', 'Stage 2 - MCQ' if shortlisted else 'Rejected at CV Stage')
        logger.success(f"CV result updated for {email}: {cv_score}/100")
        return True
    except Exception as e:
        logger.error(f"Failed to update CV result: {e}")
        return False

def update_mcq_result(email, mcq_score, passed):
    """Updates MCQ scoring columns."""
    try:
        session = get_write_session()
        row_num = _find_row_by_email(session, email)
        if not row_num:
            logger.warning(f"Candidate {email} not found in sheet for MCQ update.")
            return False
        _update_cell(session, row_num, 'J', round(mcq_score, 1) if mcq_score is not None else '')
        _update_cell(session, row_num, 'K', 'Shortlisted' if passed else 'Not Selected')
        _update_cell(session, row_num, 'N', 'Stage 3 - Voice Interview' if passed else 'Rejected at MCQ Stage')
        logger.success(f"MCQ result updated for {email}: {mcq_score}/100")
        return True
    except Exception as e:
        logger.error(f"Failed to update MCQ result: {e}")
        return False

def update_voice_result(email, voice_score, passed):
    """Updates voice interview scoring columns."""
    try:
        session = get_write_session()
        row_num = _find_row_by_email(session, email)
        if not row_num:
            logger.warning(f"Candidate {email} not found in sheet for voice update.")
            return False
        _update_cell(session, row_num, 'L', round(voice_score, 1) if voice_score is not None else '')
        _update_cell(session, row_num, 'M', 'Shortlisted' if passed else 'Not Selected')
        _update_cell(session, row_num, 'N', 'Final Shortlist' if passed else 'Rejected at Voice Stage')
        logger.success(f"Voice result updated for {email}: {voice_score}/100")
        return True
    except Exception as e:
        logger.error(f"Failed to update voice result: {e}")
        return False

def sync_all_from_mongodb():
    """
    Backfill: reads all candidates from MongoDB and writes them to the sheet.
    Safe to call on existing sheets — skips candidates already present.
    Call this once to populate the sheet with historical data.
    """
    try:
        from database.mongodb import db_manager
        from scoring.pipeline import get_job_title
        candidates = list(db_manager.candidates.find({}))
        logger.info(f"Syncing {len(candidates)} candidates to Google Sheet...")
        for c in candidates:
            email     = c.get('email', '')
            job_title = ''
            try:
                from bson import ObjectId
                job = db_manager.jobs.find_one({'_id': ObjectId(c.get('job_id', ''))})
                job_title = job.get('title', '') if job else ''
            except Exception:
                pass

            # Add row if missing
            add_candidate(c, job_title)

            # Update CV result if scored
            if c.get('final_score') is not None:
                shortlisted = c.get('status') not in ['not_selected', 'received', 'processing', 'scored']
                update_cv_result(
                    email,
                    c.get('final_score'),
                    shortlisted,
                    education=str(c.get('education', '') or ''),
                    experience=str(c.get('work_experience', '') or ''),
                    skills=', '.join(c.get('skills_extracted', []) or []),
                    full_name=c.get('full_name', ''),
                    job_title=job_title
                )

            # Update MCQ result if scored
            if c.get('mcq_score') is not None:
                mcq_passed = c.get('mcq_passed', False) or c.get('status') in ['mcq_passed', 'interviewing', 'interview_done']
                update_mcq_result(email, c.get('mcq_score'), mcq_passed)

            # Update voice result if scored
            if c.get('voice_score') is not None:
                voice_passed = c.get('status') in ['interview_done', 'final_shortlist']
                update_voice_result(email, c.get('voice_score'), voice_passed)

        logger.success(f"Sheet sync complete. {len(candidates)} candidates processed.")
        return True
    except Exception as e:
        logger.error(f"Sheet sync failed: {e}")
        return False
