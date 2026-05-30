# AI-Powered Automated Recruitment & Candidate Screening System

**Course:** CSC-233 Artificial Intelligence Lab, Spring 2026  
**Institution:** Beaconhouse National University  
**Instructor:** Hafiz Muhammad Abubakar  

---

## What This System Does

An end-to-end recruitment automation platform that processes candidates through three sequential AI-powered stages — entirely offline with zero AI API costs.

- **Stage 1 — CV Screening:** Candidates submit via Google Form. A local LLM (LLaMA3 / phi3:mini via Ollama) scores each CV against 7 weighted parameters. Score ≥ 65 → shortlisted.
- **Stage 2 — MCQ Test:** Shortlisted candidates receive a Google Forms test link. The LLM evaluates answers automatically. Score ≥ 60 → advances.
- **Stage 3 — Voice Interview:** AI conducts a live voice interview. faster-whisper transcribes speech (English + Urdu). SBERT scores answers semantically. Score ≥ 50 → final shortlist.

All candidate data is written to MongoDB Atlas and a Google Sheet in real time. An HTML analytics dashboard shows pipeline metrics for management.

---

## Repository Structure

```
recruitment-ai/
├── api/                     FastAPI REST backend
├── backend/                 All pipeline modules
│   ├── scoring/             LLM scorer, tenure calculator, MCQ scorer
│   ├── intake/              Google Drive poller, MCQ poller
│   ├── extraction/          PDF and DOCX text extraction
│   ├── notifications/       Gmail SMTP email sender
│   ├── voice_interview_lib/ Standalone voice library (STT, TTS, SBERT)
│   ├── database/            MongoDB Atlas connection manager
│   └── config/              Settings loader
├── frontend/
│   ├── ui/                  Streamlit employer dashboard
│   └── dashboard/           HTML analytics dashboard (Chart.js)
├── model/
│   ├── notebook.ipynb       Data processing & model evaluation notebook
│   └── MODELS.md            AI model documentation
├── dataset/                 Processed dataset and processing script
├── docs/                    Project proposal, TDP, technical documentation
├── poster/                  Project poster
├── .env.example             Configuration template (no real values)
├── requirements.txt         Python dependencies
└── start.sh                 Quick start script
```

---

## Technology Stack

| Component | Technology |
|---|---|
| LLM Runtime | Ollama (local) — LLaMA3 / phi3:mini / Mistral |
| CV Scoring | 7-parameter weighted scoring (6 LLM + 1 rule-based) |
| Speech-to-Text | faster-whisper (local, free, English + Urdu) |
| Text-to-Speech | Coqui TTS / pyttsx3 (offline) |
| Answer Scoring | SBERT all-MiniLM-L6-v2 (semantic similarity) |
| CV Parsing | pdfminer.six, python-docx |
| Database | MongoDB Atlas (free M0 tier) |
| Backend | FastAPI + Uvicorn |
| Employer UI | Streamlit |
| Analytics Dashboard | HTML + Chart.js |
| Email | Gmail SMTP |
| Candidate Sheet | Google Sheets API |

**Total AI running cost: PKR 0** — all models run locally, no paid APIs.

---

## Setup Instructions

### Requirements
- macOS 12+ or Windows 10+
- Python 3.11
- 8GB RAM minimum (16GB recommended)
- 20GB free disk space
- Homebrew (macOS)

### Step 1 — Install Ollama and download a model
```bash
brew install ollama
brew services start ollama
ollama pull phi3:mini
```

### Step 2 — Clone the repo and set up Python environment
```bash
git clone https://github.com/fatimahhadeell-hub/Recruitment-ai.git
cd Recruitment-ai
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Step 3 — Configure environment variables
```bash
cp .env.example .env
nano .env
```

Fill in all values marked as `<your_value_here>`:
- `MONGODB_URI` — your MongoDB Atlas connection string
- `SMTP_PASSWORD` — your Gmail App Password
- `GOOGLE_*` IDs — your Google Drive, Sheets, and Forms IDs

### Step 4 — Add Google credentials
Place your `service_account.json` file in the `credentials/` folder.  
This file is not included in the repo for security reasons.  
Generate it at: console.cloud.google.com → APIs & Services → Credentials → Service Account.

### Step 5 — Start the system
```bash
# Terminal 1 — FastAPI backend
uvicorn api:app --host 127.0.0.1 --port 8000

# Terminal 2 — Streamlit employer dashboard
streamlit run ui/__init__.py --server.port 8501

# Terminal 3 — HTML analytics dashboard (optional)
cd dashboard && python3.11 -m http.server 8080
```

Open browser at:
- Employer dashboard: http://localhost:8501
- Analytics dashboard: http://localhost:8080

---

## CV Scoring Parameters

| Parameter | Weight | Method |
|---|---|---|
| Education Relevance | 20% | LLM |
| Work Experience | 25% | LLM |
| Skills Match | 20% | LLM |
| Job Stability / Tenure | 10% | Rule-based (spaCy + dateutil) |
| Career Progression | 10% | LLM |
| Values & Ethics | 10% | LLM |
| Communication Quality | 5% | LLM |

---

## AI Models Used

| Model | Purpose | How to Get |
|---|---|---|
| LLaMA3 / phi3:mini | CV scoring, MCQ evaluation, interview questions | `ollama pull llama3` or `ollama pull phi3:mini` |
| SBERT all-MiniLM-L6-v2 | Interview answer scoring | Auto-downloaded via `sentence-transformers` |
| faster-whisper (base) | Speech-to-text transcription | Auto-downloaded via `faster-whisper` |
| Coqui TTS / pyttsx3 | Text-to-speech for interview questions | Installed via `pip install TTS pyttsx3` |

All models run locally. No API keys required after initial download.

---

## Troubleshooting

| Error | Fix |
|---|---|
| `Ollama connection refused` | Run: `brew services start ollama` |
| `SSL: CERTIFICATE_VERIFY_FAILED` | Add `tlsAllowInvalidCertificates=True` to MongoClient (macOS 12 only) |
| `ModuleNotFoundError` | Run: `cd recruitment_ai && source venv/bin/activate` |
| `Port 8000 already in use` | Run: `pkill -f 'uvicorn api:app'` |
| `Google Sheets 400 error` | URL-encode sheet name: `Form+responses+1%21A%3AZ` |

---

## Security Notes

- Never commit your `.env` file — it is listed in `.gitignore`
- Never commit `credentials/service_account.json` — it is listed in `.gitignore`
- Use `.env.example` as a template — replace all `<placeholder>` values locally
- Use Gmail App Passwords, not your main Gmail password

---

*Beaconhouse National University — CSC-233 AI Lab, Spring 2026*
