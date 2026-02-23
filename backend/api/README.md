# Hospital Pre-Consultation API

FastAPI backend that orchestrates Models A–F into a single patient session pipeline.

## Project Structure

```
api/
├── main.py               # App entry point
├── session.py            # Session store and data types
├── requirements.txt
├── .env.example          # Copy to .env and fill in values
├── models/
│   ├── model_a.py        # Speech-to-text (Whisper)
│   ├── model_b.py        # Clinical extraction (Gemini)
│   ├── model_c.py        # Question selection (Gemini)
│   ├── model_d.py        # Risk scoring (Gemini)
│   ├── model_e.py        # Patient message (Gemini)
│   └── model_f.py        # Doctor brief (Gemini)
└── routers/
    ├── sessions.py       # Session lifecycle
    ├── transcription.py  # Audio intake → Models A + B + first C question
    ├── dialogue.py       # Answer loop → Model C
    └── triage.py         # Finalise → Models D + E + F
```

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env          # then add your GEMINI_API_KEY
uvicorn main:app --reload --port 8000
```

Interactive API docs: http://localhost:8000/docs

---

## Session Flow

A patient session follows this sequence of API calls:

```
1. POST /sessions
   → Creates session, returns session_id

2. POST /sessions/{id}/audio      (multipart, send audio file)
   → Transcribes audio (Model A)
   → Extracts clinical info (Model B)
   → Returns first question (Model C)

3. POST /sessions/{id}/answer     (repeat until coverage_complete = true)
   → Records answer
   → Updates extraction (Model B)
   → Returns next question (Model C)
   → When done: returns coverage_complete = true

4. POST /sessions/{id}/complete
   → Scores urgency (Model D)
   → Generates patient message (Model E)
   → Generates doctor brief (Model F)
   → Returns both outputs

5. DELETE /sessions/{id}          (optional cleanup)
```

---

## Endpoints

### Session Management

| Method | Path | Description |
|--------|------|-------------|
| POST | `/sessions` | Start a new patient session |
| GET | `/sessions/{id}` | Inspect session state |
| DELETE | `/sessions/{id}` | End and clean up session |

### Pipeline

| Method | Path | Description |
|--------|------|-------------|
| POST | `/sessions/{id}/audio` | Submit audio → runs Models A, B, first C |
| POST | `/sessions/{id}/answer` | Submit answer → runs B update + next C |
| POST | `/sessions/{id}/complete` | Finalise → runs Models D, E, F |

---

## Example: Full Session (curl)

```bash
# 1. Start session
SESSION=$(curl -s -X POST http://localhost:8000/sessions \
  -H "Content-Type: application/json" \
  -d '{"language": "english", "patient_age": 54, "location": "Waiting Area B"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['session_id'])")

# 2. Submit audio
curl -X POST http://localhost:8000/sessions/$SESSION/audio \
  -F "audio=@patient_audio.wav"

# 3. Submit answer (repeat as needed)
curl -X POST http://localhost:8000/sessions/$SESSION/answer \
  -H "Content-Type: application/json" \
  -d '{"question": "How severe is the pain?", "answer": "About eight out of ten."}'

# 4. Finalise
curl -X POST http://localhost:8000/sessions/$SESSION/complete
```

---

## Notes

- **Session state** is held in memory. On server restart all sessions are lost.
  Swap `session.py`'s `_store` dict for Redis or a database for production.

- **Whisper models** load once at startup (`lifespan` in `main.py`).
  First load downloads ~3 GB of weights. Subsequent starts use the cache.

- **MAX_TURNS** (default 6) controls how many Model C questions are asked
  before coverage is considered complete. Set in `.env`.

- The `/docs` endpoint (FastAPI's built-in Swagger UI) lets you test all
  endpoints interactively without writing any client code.
