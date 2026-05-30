
import subprocess
import tempfile
import os
from loguru import logger

def speak(text, language='en'):
    """
    Speaks text aloud using macOS built-in say command.
    Completely free, offline, no limits.
    language: 'en' for English, 'ur' for Urdu
    """
    # macOS voices for each language
    voices = {
        'en': 'Samantha',   # Clear English voice built into macOS
        'ur': 'Samantha',   # Fall back to English if Urdu voice not installed
    }
    voice = voices.get(language, 'Samantha')
    logger.debug(f"Speaking ({language}): {text[:60]}...")
    subprocess.run(['say', '-v', voice, text])

def speak_to_file(text, output_path, language='en'):
    """
    Converts text to speech and saves as audio file.
    Useful for playing back later or reviewing.
    """
    voices = {'en': 'Samantha', 'ur': 'Samantha'}
    voice = voices.get(language, 'Samantha')
    subprocess.run(['say', '-v', voice, '-o', output_path, '--data-format=LEF32@22050', text])
    return output_path

def get_available_voices():
    """Lists all voices installed on this Mac."""
    result = subprocess.run(['say', '-v', '?'], capture_output=True, text=True)
    voices = []
    for line in result.stdout.split('\n'):
        if line.strip():
            parts = line.split()
            if parts:
                voices.append(parts[0])
    return voices
