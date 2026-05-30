import re
from pathlib import Path
from typing import Optional
from pdfminer.high_level import extract_text as pdf_extract_text
from docx import Document as DocxDocument
from loguru import logger
from database.mongodb import db_manager
from models.schemas import CandidateStatus
import datetime

def extract_text_from_pdf(file_path: str) -> Optional[str]:
    """Extract raw text from a PDF file using pdfminer.six."""
    try:
        text = pdf_extract_text(file_path)
        if not text or not text.strip():
            logger.warning(f"PDF extracted but no text found: {file_path}")
            return None
        logger.debug(f"PDF extracted: {len(text)} characters from {file_path}")
        return text.strip()
    except Exception as e:
        logger.error(f"Failed to extract PDF text from {file_path}: {e}")
        return None

def extract_text_from_docx(file_path: str) -> Optional[str]:
    """Extract raw text from a DOCX file using python-docx."""
    try:
        doc = DocxDocument(file_path)
        paragraphs = [para.text for para in doc.paragraphs if para.text.strip()]
        text = "\n".join(paragraphs)
        if not text.strip():
            logger.warning(f"DOCX extracted but no text found: {file_path}")
            return None
        logger.debug(f"DOCX extracted: {len(text)} characters from {file_path}")
        return text.strip()
    except Exception as e:
        logger.error(f"Failed to extract DOCX text from {file_path}: {e}")
        return None

def extract_text_from_cv(file_path: str) -> Optional[str]:
    """
    Extract text from a CV file. Supports PDF and DOCX formats.
    Automatically detects file type from extension.
    """
    path = Path(file_path)
    if not path.exists():
        logger.error(f"CV file not found: {file_path}")
        return None
    ext = path.suffix.lower()
    if ext == ".pdf":
        return extract_text_from_pdf(file_path)
    elif ext in [".docx", ".doc"]:
        return extract_text_from_docx(file_path)
    else:
        logger.error(f"Unsupported file type: {ext}")
        return None

def process_pending_candidates() -> dict:
    """
    Finds all candidates with status RECEIVED, extracts text from their CVs,
    saves the text to MongoDB Atlas, and updates status to PROCESSING.
    Returns a summary dict with counts.
    """
    result = {"processed": 0, "failed": 0, "skipped": 0}

    # Find all candidates waiting for text extraction
    pending = list(db_manager.candidates.find({"status": CandidateStatus.RECEIVED.value}))
    logger.info(f"Text extraction: found {len(pending)} candidates with status RECEIVED.")

    for candidate in pending:
        candidate_id = candidate["_id"]
        name         = candidate.get("full_name", "Unknown")
        cv_path      = candidate.get("cv_file_path")

        if not cv_path:
            logger.warning(f"Candidate {name} has no cv_file_path. Skipping.")
            result["skipped"] += 1
            continue

        # Extract text from the CV file
        logger.info(f"Extracting text from CV for: {name}")
        raw_text = extract_text_from_cv(cv_path)

        if not raw_text:
            # Mark as error if extraction fails
            db_manager.candidates.update_one(
                {"_id": candidate_id},
                {"$set": {
                    "status":        CandidateStatus.ERROR.value,
                    "error_message": f"Could not extract text from CV file: {cv_path}",
                    "updated_at":    datetime.datetime.utcnow()
                }}
            )
            result["failed"] += 1
            logger.error(f"Text extraction failed for: {name}")
            continue

        # Save extracted text and update status to PROCESSING
        db_manager.candidates.update_one(
            {"_id": candidate_id},
            {"$set": {
                "raw_cv_text": raw_text,
                "status":      CandidateStatus.PROCESSING.value,
                "updated_at":  datetime.datetime.utcnow()
            }}
        )
        result["processed"] += 1
        logger.success(f"Text extracted for {name}: {len(raw_text)} characters. Status -> PROCESSING.")

    logger.info(f"Text extraction complete. Processed: {result['processed']}, Failed: {result['failed']}, Skipped: {result['skipped']}")
    return result
