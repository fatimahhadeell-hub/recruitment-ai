
from faster_whisper import WhisperModel
from loguru import logger

_model = None

def get_model(model_size='small'):
    """
    Loads the Whisper model once and reuses it.
    model_size: 'tiny' (39MB), 'base' (74MB), 'small' (244MB)
    Larger = more accurate but slower.
    """
    global _model
    if _model is None:
        logger.info(f"Loading Whisper model ({model_size})... this takes 30 seconds the first time.")
        _model = WhisperModel(model_size, device='cpu', compute_type='int8')
        logger.success(f"Whisper model loaded: {model_size}")
    return _model

def transcribe(audio_file_path, model_size='small', translate_to_english=True):
    """
    Transcribes an audio file to text.
    audio_file_path: path to WAV file
    translate_to_english: if True, Urdu speech becomes English text
    Returns: (text, detected_language)
    """
    model = get_model(model_size)
    task = 'translate' if translate_to_english else 'transcribe'
    segments, info = model.transcribe(audio_file_path, task=task)
    text = ' '.join([segment.text for segment in segments]).strip()
    detected_lang = info.language
    logger.debug(f"Transcribed ({detected_lang}): {text[:100]}")
    return text, detected_lang
