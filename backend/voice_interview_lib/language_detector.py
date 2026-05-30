
from langdetect import detect, DetectorFactory
from loguru import logger

# Set seed for consistent results
DetectorFactory.seed = 42

SUPPORTED_LANGUAGES = {
    'en': 'English',
    'ur': 'Urdu',
}

def detect_language(text):
    """
    Detects whether text is English or Urdu.
    Returns language code: 'en' or 'ur'
    Defaults to 'en' if detection fails or language not supported.
    """
    if not text or not text.strip():
        return 'en'
    try:
        lang = detect(text)
        if lang in SUPPORTED_LANGUAGES:
            logger.debug(f"Language detected: {SUPPORTED_LANGUAGES[lang]}")
            return lang
        else:
            logger.debug(f"Unsupported language detected ({lang}), defaulting to English")
            return 'en'
    except Exception as e:
        logger.warning(f"Language detection failed: {e}. Defaulting to English.")
        return 'en'

def is_urdu(text):
    """Returns True if the text is Urdu."""
    return detect_language(text) == 'ur'

def is_english(text):
    """Returns True if the text is English."""
    return detect_language(text) == 'en'
