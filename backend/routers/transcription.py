"""
routers/transcription.py — Audio intake endpoint.

POST /sessions/{id}/audio
  → Runs Model A (speech-to-text)
  → Runs Model B (clinical extraction)
  → Returns transcription and extraction only (no questions)
"""

import os
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from typing import Optional

from session import get_session, SessionStage, ConversationTurn
from models import model_a, model_b

MAX_TURNS = int(os.getenv("MAX_TURNS", 6))

router = APIRouter(prefix="/sessions", tags=["transcription"])


@router.post("/{session_id}/audio")
async def receive_audio(
    session_id: str,
    audio: UploadFile = File(...),
    language: Optional[str] = Form(None),  # override auto-detection if known
):
    """
    Accept a patient audio file, transcribe it, and extract clinical information.
    Does NOT return questions - use the dialogue API for that.

    Transitions session: AWAITING_AUDIO → AWAITING_AUDIO (stays ready for more processing)
    """
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")
    if session.stage != SessionStage.AWAITING_AUDIO:
        raise HTTPException(status_code=409, detail=f"Session is in stage '{session.stage.value}', not awaiting audio.")

    audio_bytes = await audio.read()

    # Model A — transcribe
    try:
        a_result = model_a.transcribe(audio_bytes, language=language or session.language)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Transcription failed: {e}")

    session.transcript      = a_result["full_text"]
    session.transcript_conf = a_result["mean_confidence"]
    if not language:
        session.language    = a_result["dominant_language"]

    # Model B — extract
    try:
        session.extraction = model_b.extract(session.transcript)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Extraction failed: {e}")

    # Note: Session stage remains AWAITING_AUDIO until dialogue begins
    # Call /sessions/{id}/question to start the dialogue and get first question

    return {
        "session_id":          session.id,
        "stage":               session.stage.value,
        "transcript":          session.transcript,
        "transcript_language": session.language,
        "transcript_confidence": session.transcript_conf,
        "extraction":          session.extraction,
    }
