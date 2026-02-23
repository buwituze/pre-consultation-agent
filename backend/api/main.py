"""
main.py — FastAPI application entry point.

Run with:
    uvicorn main:app --reload --port 8000

Interactive docs available at:
    http://localhost:8000/docs
"""

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from contextlib import asynccontextmanager

from models import model_a
from routers import sessions, transcription, dialogue, triage


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Load Whisper models once at startup — this takes ~1-2 min on first run
    model_a.load_models()
    yield
    # Nothing to clean up on shutdown


app = FastAPI(
    title="Hospital Pre-Consultation API",
    description="Voice-based triage pipeline for Kinyarwanda and English patients.",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(sessions.router)
app.include_router(transcription.router)
app.include_router(dialogue.router)
app.include_router(triage.router)


@app.get("/health")
def health():
    return {"status": "ok"}
