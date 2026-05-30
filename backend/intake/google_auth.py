from pathlib import Path
from typing import Optional
from google.oauth2 import service_account
from google.oauth2.service_account import Credentials
import google.auth.transport.requests
from loguru import logger
from config.settings import settings

GOOGLE_SCOPES = [
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/spreadsheets.readonly",
]

def get_google_credentials() -> Optional[Credentials]:
    creds_path = Path(settings.GOOGLE_CREDENTIALS_FILE)
    if not creds_path.exists():
        logger.warning(f"Google credentials file not found at: {creds_path}")
        return None
    try:
        credentials = service_account.Credentials.from_service_account_file(
            str(creds_path), scopes=GOOGLE_SCOPES
        )
        # Pre-refresh token using requests transport to avoid httplib2 timeout issues
        auth_req = google.auth.transport.requests.Request()
        credentials.refresh(auth_req)
        logger.debug(f"Google credentials loaded and token refreshed. Service account: {credentials.service_account_email}")
        return credentials
    except Exception as e:
        logger.error(f"Error loading Google credentials: {e}")
        return None

def validate_credentials() -> bool:
    return get_google_credentials() is not None

def get_authorized_session():
    creds = get_google_credentials()
    if creds is None:
        return None
    return google.auth.transport.requests.AuthorizedSession(creds)
