
import datetime
import os
from loguru import logger
from sentence_transformers import SentenceTransformer, util
from voice_interview_lib.recorder import record_audio
from voice_interview_lib.transcriber import transcribe
from voice_interview_lib.synthesizer import speak
from voice_interview_lib.language_detector import detect_language

_sbert_model = None

def get_sbert():
    global _sbert_model
    if _sbert_model is None:
        _sbert_model = SentenceTransformer('all-MiniLM-L6-v2')
        logger.success("SBERT model loaded for voice interview scoring.")
    return _sbert_model

def score_answer(candidate_answer, ideal_answer):
    """
    Scores how well the candidate answer matches the ideal answer.
    Uses SBERT semantic similarity (0.0 to 1.0).
    Multiply by 100 for a percentage score.
    """
    if not candidate_answer or not candidate_answer.strip():
        return 0.0
    model = get_sbert()
    embeddings = model.encode([candidate_answer, ideal_answer], convert_to_tensor=True)
    similarity = util.cos_sim(embeddings[0], embeddings[1]).item()
    return round(max(0.0, min(1.0, similarity)), 4)


class VoiceInterviewer:
    """
    Conducts a complete voice interview session.
    Can be used independently in any Python project:

        from voice_interview_lib import VoiceInterviewer
        interviewer = VoiceInterviewer()
        result = interviewer.conduct_interview(questions)
    """

    def __init__(self, model_size='small', recording_seconds=45):
        self.model_size = model_size
        self.recording_seconds = recording_seconds
        self.transcript = []
        self.current_language = 'en'

    def conduct_interview(self, questions):
        """
        Conducts a complete voice interview.
        questions: list of dicts with 'question_text' and 'ideal_answer' keys
        Returns: dict with transcript, scores, overall_score
        """
        self.transcript = []
        scores = []

        speak("Welcome to the AI interview. I will ask you questions one by one.")
        speak("Please speak your answer clearly after each question.")
        speak("You may answer in English or Urdu. The system understands both.")

        for i, q in enumerate(questions):
            question_text = q.get('question_text', q.get('question', ''))
            ideal_answer  = q.get('ideal_answer', '')

            print(f"\nQuestion {i+1} of {len(questions)}")
            print(f"Q: {question_text}")

            # Speak the question aloud
            speak(f"Question {i+1}: {question_text}", self.current_language)

            # Record the candidate's answer
            audio_file = record_audio(duration_seconds=self.recording_seconds)

            # Transcribe the audio to English text
            transcript_text, detected_lang = transcribe(
                audio_file,
                model_size=self.model_size,
                translate_to_english=True
            )

            # Update current language based on what candidate spoke
            self.current_language = detected_lang if detected_lang in ['en', 'ur'] else 'en'

            print(f"Detected language: {detected_lang}")
            print(f"Transcribed: {transcript_text}")

            # Score the answer
            similarity = score_answer(transcript_text, ideal_answer)
            score_pct  = round(similarity * 100, 1)

            print(f"Score: {score_pct}/100")

            # Give brief feedback
            if similarity > 0.6:
                speak("Thank you. That was a strong answer.", self.current_language)
            elif similarity > 0.3:
                speak("Thank you. Moving to the next question.", self.current_language)
            else:
                speak("Thank you. Let us continue.", self.current_language)

            # Clean up temp audio file
            try:
                os.remove(audio_file)
            except Exception:
                pass

            scores.append(similarity)
            self.transcript.append({
                'question_number':  i + 1,
                'question_text':    question_text,
                'answer_text':      transcript_text,
                'language_detected':detected_lang,
                'similarity_score': similarity,
                'score_percent':    score_pct,
                'ideal_answer':     ideal_answer,
            })

        overall_score = round((sum(scores) / len(scores)) * 100, 1) if scores else 0.0

        speak(f"Interview complete. Thank you for your time.")
        print(f"\nOverall Interview Score: {overall_score}/100")

        return {
            'transcript':     self.transcript,
            'scores':         scores,
            'overall_score':  overall_score,
            'completed_at':   datetime.datetime.utcnow().isoformat(),
            'questions_count':len(questions),
        }
