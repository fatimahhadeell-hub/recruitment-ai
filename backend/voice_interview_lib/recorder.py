
import sounddevice as sd
import numpy as np
import wave
import tempfile
import os

SAMPLE_RATE = 16000  # 16000 Hz is the standard for speech recognition

def record_audio(duration_seconds=45):
    """
    Records audio from the default microphone.
    duration_seconds: maximum recording time
    Returns: path to saved WAV file
    """
    print(f"Recording... speak now (max {duration_seconds} seconds)")
    print("Press Ctrl+C to stop recording early")
    try:
        recording = sd.rec(
            int(duration_seconds * SAMPLE_RATE),
            samplerate=SAMPLE_RATE,
            channels=1,
            dtype='int16'
        )
        sd.wait()
    except KeyboardInterrupt:
        sd.stop()
        print("Recording stopped.")

    tmp = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)
    with wave.open(tmp.name, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(recording.tobytes())

    print(f"Audio saved: {tmp.name}")
    return tmp.name

def play_audio(file_path):
    """Plays a WAV file through the speakers."""
    import subprocess
    subprocess.run(['afplay', file_path])
