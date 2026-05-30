from __future__ import annotations
from pathlib import Path
from pydantic_settings import BaseSettings

CONFIG_DIR   = Path(__file__).resolve().parent
PROJECT_ROOT = CONFIG_DIR.parent
CV_DOWNLOAD_DIR = PROJECT_ROOT / "data" / "cv_downloads"
CREDENTIALS_DIR = PROJECT_ROOT / "credentials"
LOG_DIR         = PROJECT_ROOT / "logs"

CV_DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
CREDENTIALS_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)

class Settings(BaseSettings):
    APP_NAME:    str = "Recruitment AI"
    APP_VERSION: str = "1.0.0"
    DEBUG_MODE:  bool = False
    MONGODB_URI:      str = "mongodb://localhost:27017"
    MONGODB_DATABASE: str = "recruitment_ai"
    COLLECTION_JOBS:          str = "jobs"
    COLLECTION_CANDIDATES:    str = "candidates"
    COLLECTION_SCORES:        str = "scores"
    COLLECTION_INTERVIEWS:    str = "interviews"
    COLLECTION_NOTIFICATIONS: str = "notifications"
    COLLECTION_CONFIG:        str = "system_config"
    OLLAMA_HOST:    str = "http://localhost:11434"
    OLLAMA_MODEL: str = "mistral"
    OLLAMA_TIMEOUT: int = 120
    SBERT_MODEL: str = "all-MiniLM-L6-v2"
    GOOGLE_CREDENTIALS_FILE:      str = str(CREDENTIALS_DIR / "service_account.json")
    GOOGLE_DRIVE_FOLDER_ID:       str = ""
    GOOGLE_SHEETS_ID:             str = ""
    GOOGLE_POLL_INTERVAL_SECONDS: int = 300
    GOOGLE_MCQ_SHEETS_ID: str = ''
    GOOGLE_CANDIDATE_SHEET_ID: str = ''
    MCQ_DEADLINE_DAYS: int = 3
    MCQ_THRESHOLD: int = 60
    VOICE_THRESHOLD: int = 50
    WEIGHT_EDUCATION:     float = 0.20
    WEIGHT_EXPERIENCE:    float = 0.25
    WEIGHT_SKILLS:        float = 0.20
    WEIGHT_STABILITY:     float = 0.10
    WEIGHT_PROGRESSION:   float = 0.10
    WEIGHT_VALUES:        float = 0.10
    WEIGHT_COMMUNICATION: float = 0.05
    SERVER_IP: str = "192.168.18.14"
    SHORTLIST_THRESHOLD: int = 65
    MIN_TENURE_MONTHS:   int = 12
    SMTP_ENABLED:      bool = False
    SMTP_HOST:         str  = "localhost"
    SMTP_PORT:         int  = 25
    SMTP_USERNAME:     str  = ""
    SMTP_PASSWORD:     str  = ""
    SMTP_SENDER_EMAIL: str  = "recruitment@company.com"
    SMTP_SENDER_NAME:  str  = "Recruitment Team"
    API_HOST:   str = "127.0.0.1"
    API_PORT:   int = 8000
    API_PREFIX: str = "/api/v1"
    UI_PORT:    int = 8501
    LOG_LEVEL: str = "INFO"
    LOG_FILE:  str = str(LOG_DIR / "recruitment_ai.log")

    class Config:
        env_file = str(PROJECT_ROOT / ".env")
        case_sensitive = False

settings = Settings()

def validate_weights() -> None:
    total = round(
        settings.WEIGHT_EDUCATION + settings.WEIGHT_EXPERIENCE +
        settings.WEIGHT_SKILLS   + settings.WEIGHT_STABILITY   +
        settings.WEIGHT_PROGRESSION + settings.WEIGHT_VALUES   +
        settings.WEIGHT_COMMUNICATION, 10
    )
    if total != 1.0:
        raise ValueError(f"Scoring weights must sum to 1.0 but got {total:.4f}")

validate_weights()
