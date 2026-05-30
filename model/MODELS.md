# AI Models Documentation

**Project:** AI-Powered Automated Recruitment & Candidate Screening System  
**Course:** CSC-233 Artificial Intelligence Lab, Spring 2026  
**Institution:** Beaconhouse National University  

---

## Why Pre-Trained Models

This project uses pre-trained models rather than training from scratch. This is a deliberate architectural decision, not a limitation:

1. **Scale:** Models like LLaMA3 were trained on trillions of tokens. Training an equivalent model from scratch would require millions of dollars and months of compute time — impossible for a university project.
2. **Zero Cost Requirement:** A core project requirement is zero AI running cost. Pre-trained models downloaded once and run locally perfectly satisfy this.
3. **Industry Standard:** In real-world AI engineering, using and integrating pre-trained models is the standard practice. Fine-tuning or prompting a pre-trained LLM is how virtually all production AI systems are built today.
4. **Custom Logic:** The system does include a fully custom-built model — the Tenure Calculator — which is rule-based arithmetic built entirely from scratch using spaCy and dateutil.

---

## Model 1 — LLaMA3 / phi3:mini (LLM Scoring)

| Property | Value |
|---|---|
| **Model Name** | LLaMA3 (Meta) or phi3:mini (Microsoft) |
| **Runtime** | Ollama (local, offline) |
| **Size** | LLaMA3: 4.7GB / phi3:mini: 2.2GB |
| **Purpose** | Scores 6 of 7 CV parameters, evaluates MCQ answers, generates interview questions |
| **Cost** | Free forever — runs on local CPU/GPU |
| **Internet Required** | Download once only. Runs offline permanently after that. |

**How to download:**
```bash
ollama pull llama3       # recommended
# OR
ollama pull phi3:mini    # lighter, faster on older hardware
```

**How it is used in this project:**

The LLM receives a structured prompt containing the job description and the candidate's CV text. It returns a JSON object with scores (0-10) and one-sentence justifications for each of these parameters:
- Education Relevance (20% weight)
- Work Experience Relevance (25% weight)
- Skills Match (20% weight)
- Career Progression (10% weight)
- Values & Ethics (10% weight)
- Communication Quality (5% weight)

Temperature is set to 0.1 (near-deterministic) so scores are consistent and reproducible.

---

## Model 2 — SBERT all-MiniLM-L6-v2 (Interview Scoring)

| Property | Value |
|---|---|
| **Model Name** | all-MiniLM-L6-v2 |
| **Source** | Hugging Face (sentence-transformers) |
| **Size** | ~90MB |
| **Purpose** | Scores voice interview answers by computing semantic similarity |
| **Cost** | Free forever — Apache 2.0 licence |
| **Internet Required** | Download once only. Cached locally at `~/.cache/huggingface/` |

**How to download:**
```bash
pip install sentence-transformers
# Model auto-downloads on first use:
python3 -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"
```

**How it is used in this project:**

When a candidate answers an interview question verbally, their transcribed answer and the ideal answer are both converted to 384-dimensional vector embeddings. Cosine similarity between the two vectors produces a score from 0.0 to 1.0. This measures semantic meaning, not just keyword overlap — so a candidate who says "I enjoy working with others" scores highly against an ideal answer about teamwork even without using the exact same words.

---

## Model 3 — faster-whisper base (Speech-to-Text)

| Property | Value |
|---|---|
| **Model Name** | Whisper base (via faster-whisper) |
| **Source** | OpenAI Whisper weights, CTranslate2 optimised |
| **Size** | 74MB (base) / 244MB (small) |
| **Purpose** | Transcribes candidate speech to text during voice interviews |
| **Languages** | English and Urdu (and 97 other languages) |
| **Cost** | Free forever — MIT licence |
| **Internet Required** | Download once only. Fully offline after that. |

**How to download:**
```bash
pip install faster-whisper
# Model auto-downloads on first use
```

**How it is used in this project:**

The candidate speaks their interview answer into the microphone. The audio is recorded as a WAV file using sounddevice. faster-whisper then transcribes the audio to text. It automatically detects whether the candidate is speaking English or Urdu and transcribes accordingly. The transcribed text is then passed to SBERT for scoring.

**Why faster-whisper instead of OpenAI Whisper API:**
The OpenAI Whisper API costs money per minute of audio. faster-whisper uses identical model weights but runs entirely on your local CPU with no usage limits and no cost.

---

## Model 4 — Coqui TTS / pyttsx3 (Text-to-Speech)

| Property | Value |
|---|---|
| **Model Name** | Coqui XTTS-v2 or pyttsx3 (system TTS) |
| **Purpose** | Reads interview questions aloud to the candidate |
| **Languages** | English and Urdu |
| **Cost** | Free forever — open source |
| **Internet Required** | No |

**How to download:**
```bash
pip install TTS pyttsx3
```

**How it is used in this project:**

The AI interviewer speaks each question aloud through the Mac's speakers so the candidate hears it clearly. pyttsx3 uses the Mac's built-in speech engine (no download needed). Coqui XTTS-v2 provides higher quality multilingual output including Urdu.

---

## Model 5 — Tenure Calculator (Custom Rule-Based Model)

| Property | Value |
|---|---|
| **Type** | Custom-built rule-based model |
| **Libraries** | spaCy en_core_web_lg, python-dateutil |
| **Purpose** | Calculates job stability score from employment dates in CV |
| **Weight** | 10% of final CV score |
| **Cost** | Free |

**This is the only model built entirely from scratch for this project.**

**How it works:**

1. spaCy's NER (Named Entity Recognition) extracts date entities from CV text
2. python-dateutil parses the dates into Python datetime objects
3. relativedelta calculates the duration of each role in months
4. Average tenure is computed arithmetically
5. A scoring rule converts average tenure to a score 0-10:

| Average Tenure | Score |
|---|---|
| ≥ 24 months | 10/10 |
| ≥ 18 months | 8/10 |
| ≥ 12 months | 6/10 |
| ≥ 6 months | 4/10 |
| < 6 months | 2/10 |

**How to download spaCy model:**
```bash
python3.11 -m spacy download en_core_web_lg
```

---

## Complete Model Summary

| Model | Type | Size | Offline | Cost |
|---|---|---|---|---|
| LLaMA3 / phi3:mini | Pre-trained LLM | 2-5 GB | Yes | Free |
| SBERT all-MiniLM-L6-v2 | Pre-trained embeddings | 90 MB | Yes | Free |
| faster-whisper base | Pre-trained STT | 74 MB | Yes | Free |
| Coqui TTS / pyttsx3 | Pre-trained TTS | ~1 GB | Yes | Free |
| Tenure Calculator | Custom rule-based | 0 MB | Yes | Free |
| **TOTAL** | | **~8 GB** | **100%** | **PKR 0** |

---

*Beaconhouse National University — CSC-233 AI Lab, Spring 2026*
