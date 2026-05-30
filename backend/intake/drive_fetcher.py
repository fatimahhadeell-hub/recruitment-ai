
import datetime
import re
import time
import urllib.parse
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from loguru import logger
from config.settings import settings, CV_DOWNLOAD_DIR
from database.mongodb import db_manager
from intake.google_auth import get_google_credentials, get_authorized_session
from models.schemas import CandidateDocument, CandidateStatus
try:
    from candidate_sheet import add_candidate as add_to_sheet
    SHEET_ENABLED = True
except Exception:
    SHEET_ENABLED = False
import google.auth.transport.requests

COL_TIMESTAMP = "Timestamp"
COL_NAME      = "Full Name"
COL_EMAIL     = "Email Address"
COL_PHONE     = "Phone Number"
COL_JOB_TITLE = "Job Title Applied For"
COL_CV_UPLOAD = "CV Upload"
SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".doc"}

class DriveFetcher:
    def __init__(self):
        self._session = None

    def run(self) -> Dict[str, int]:
        result = {"checked": 0, "new": 0, "skipped": 0, "errors": 0}
        if not self._connect():
            logger.warning("DriveFetcher: Google authentication failed.")
            return result
        if not settings.GOOGLE_SHEETS_ID:
            logger.warning("GOOGLE_SHEETS_ID not set in .env file.")
            return result
        rows = self._read_sheet_rows()
        if rows is None:
            return result
        result["checked"] = len(rows)
        logger.info(f"DriveFetcher: {len(rows)} total form submissions found.")
        for row in rows:
            try:
                outcome = self._process_row(row)
                result[outcome] += 1
            except Exception as e:
                logger.error(f"Error processing row: {e}", exc_info=True)
                result["errors"] += 1
        logger.info(f"DriveFetcher complete. New: {result['new']}, Skipped: {result['skipped']}, Errors: {result['errors']}")
        return result

    def _connect(self) -> bool:
        self._session = get_authorized_session()
        if self._session is None:
            return False
        logger.debug("DriveFetcher: Google API session established.")
        return True

    def _read_sheet_rows(self) -> Optional[List[Dict]]:
        try:
            range_param = "Form+responses+1%21A%3AZ"
            url = f"https://sheets.googleapis.com/v4/spreadsheets/{settings.GOOGLE_SHEETS_ID}/values/{range_param}"
            response = self._session.get(url)
            if response.status_code != 200:
                logger.error(f"Sheets API error {response.status_code}: {response.text}")
                return None
            values = response.json().get("values", [])
            if not values:
                logger.info("Google Sheet is empty - no form submissions yet.")
                return []
            headers   = values[0]
            data_rows = values[1:]
            rows_as_dicts = []
            for row in data_rows:
                padded = row + [""] * (len(headers) - len(row))
                rows_as_dicts.append(dict(zip(headers, padded)))
            logger.debug(f"Read {len(rows_as_dicts)} rows from Google Sheets.")
            return rows_as_dicts
        except Exception as e:
            logger.error(f"Failed to read Google Sheets: {e}")
            return None

    def _process_row(self, row: Dict) -> str:
        file_id = self._extract_file_id(row.get(COL_CV_UPLOAD, ""))
        if not file_id:
            return "skipped"
        if self._already_processed(file_id):
            return "skipped"
        name  = row.get(COL_NAME,  "").strip()
        email = row.get(COL_EMAIL, "").strip()
        phone = row.get(COL_PHONE, "").strip() or None
        if not name or not email:
            logger.warning(f"Row missing name or email. Skipping.")
            return "skipped"
        job_title = row.get(COL_JOB_TITLE, "").strip()
        job_id    = self._find_job_id(job_title)
        if not job_id:
            logger.warning(f"No active job found for: '{job_title}'")
            return "skipped"
        local_path, file_name = self._download_cv(file_id, name)
        if not local_path:
            return "errors"
        success = self._create_candidate_record(
            job_id=job_id, name=name, email=email, phone=phone,
            file_id=file_id, local_path=str(local_path),
            file_name=file_name, row_timestamp=row.get(COL_TIMESTAMP, ""),
            job_title=job_title
        )
        return "new" if success else "errors"

    def _extract_file_id(self, drive_url_or_id: str) -> Optional[str]:
        if not drive_url_or_id:
            return None
        match = re.search(r"[?&]id=([a-zA-Z0-9_-]+)", drive_url_or_id)
        if match:
            return match.group(1)
        match = re.search(r"/d/([a-zA-Z0-9_-]+)", drive_url_or_id)
        if match:
            return match.group(1)
        if re.match(r"^[a-zA-Z0-9_-]{25,50}$", drive_url_or_id.strip()):
            return drive_url_or_id.strip()
        return None

    def _already_processed(self, file_id: str) -> bool:
        existing = db_manager.candidates.find_one({"google_drive_file_id": file_id}, {"_id": 1})
        return existing is not None

    def _find_job_id(self, job_title_from_form: str) -> Optional[str]:
        if not job_title_from_form:
            return None
        job = db_manager.jobs.find_one(
            {"title": {"$regex": f"^{re.escape(job_title_from_form)}$", "$options": "i"}, "status": "active"},
            {"_id": 1}
        )
        return str(job["_id"]) if job else None

    def _download_cv(self, file_id: str, candidate_name: str) -> Tuple[Optional[Path], Optional[str]]:
        try:
            # Get file metadata
            meta_url  = f"https://www.googleapis.com/drive/v3/files/{file_id}?fields=name,size,mimeType"
            meta_resp = self._session.get(meta_url)
            if meta_resp.status_code != 200:
                logger.error(f"Failed to get file metadata: {meta_resp.text}")
                return None, None
            file_metadata  = meta_resp.json()
            original_name  = file_metadata.get("name", f"cv_{file_id}")
            file_extension = Path(original_name).suffix.lower()
            if file_extension not in SUPPORTED_EXTENSIONS:
                logger.warning(f"Unsupported file type: {file_extension}")
                return None, None
            safe_name      = self._sanitise_filename(candidate_name)
            timestamp      = int(time.time())
            id_prefix      = file_id[:6]
            local_filename = f"{safe_name}_{timestamp}_{id_prefix}{file_extension}"
            local_path     = CV_DOWNLOAD_DIR / local_filename
            # Download file content
            dl_url  = f"https://www.googleapis.com/drive/v3/files/{file_id}?alt=media"
            dl_resp = self._session.get(dl_url, stream=True)
            if dl_resp.status_code != 200:
                logger.error(f"Failed to download file: {dl_resp.text}")
                return None, None
            with open(local_path, "wb") as fh:
                for chunk in dl_resp.iter_content(chunk_size=8192):
                    fh.write(chunk)
            logger.success(f"CV downloaded: {original_name} -> {local_path}")
            return local_path, original_name
        except Exception as e:
            logger.error(f"Failed to download CV {file_id}: {e}")
            return None, None

    @staticmethod
    def _sanitise_filename(name: str) -> str:
        safe = re.sub(r"[^\w\s]", "", name)
        safe = re.sub(r"[\s_]+", "_", safe.strip())
        return safe[:40].lower()

    def _create_candidate_record(self, job_id, name, email, phone, file_id, local_path, file_name, row_timestamp, job_title="") -> bool:
        try:
            candidate = CandidateDocument(
                job_id=job_id, full_name=name, email=email, phone=phone,
                status=CandidateStatus.RECEIVED,
                google_drive_file_id=file_id,
                google_form_response_id=row_timestamp,
                cv_file_path=local_path, cv_file_name=file_name,
            )
            doc    = candidate.model_dump(by_alias=True, exclude_none=True)
            result = db_manager.candidates.insert_one(doc)
            logger.success(f"Candidate record created. ID: {result.inserted_id}, Name: {name}")
            if SHEET_ENABLED:
                try:
                    add_to_sheet({"full_name": name, "email": email, "phone": phone or ""}, job_title)
                except Exception as e:
                    logger.warning(f"Could not add to candidate sheet: {e}")
            return True
        except Exception as e:
            logger.error(f"Failed to create candidate record: {e}", exc_info=True)
            return False
