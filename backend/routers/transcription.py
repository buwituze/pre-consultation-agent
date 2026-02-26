"""
routers/transcription.py — Audio intake endpoint.

POST /sessions/{id}/audio
  → Runs Model A (speech-to-text)
  → Runs Model B (clinical extraction)
  → Returns transcription and extraction only (no questions)
  → Call GET /sessions/{id}/question next to start dialogue
"""

import os
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from typing import Optional

from session import get_session, SessionStage
from models import model_a, model_b

router = APIRouter(prefix="/sessions", tags=["transcription"])


@router.post("/{session_id}/audio")
async def receive_audio(
    session_id: str,
    audio:      UploadFile       = File(...),
    language:   Optional[str]    = Form(None),  # Patient's screen selection — hint only
):
    """
    Accept a patient audio file, transcribe it, and extract clinical information.
    Does not return questions — use GET /sessions/{id}/question for that.

    language (form field): passed as a hint to Model A. Detection always runs
    regardless — the selected language is never used to skip detection.

    Transitions session: AWAITING_AUDIO → AWAITING_AUDIO (stays until dialogue begins)
    """
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")
    if session.stage != SessionStage.AWAITING_AUDIO:
        raise HTTPException(
            status_code=409,
            detail=f"Session is in stage '{session.stage.value}', not awaiting audio.",
        )

    audio_bytes = await audio.read()

    # Resolve hint: prefer form field, fall back to session language if already known
    hint = language or (session.language if session.language != "unknown" else None)

    # Model A — transcribe (detection always runs; hint is tiebreaker only)
    try:
        a_result = model_a.transcribe(audio_bytes, language_hint=hint)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Transcription failed: {e}")

    session.transcript      = a_result["full_text"]
    session.transcript_conf = a_result["mean_confidence"]
    session.language        = a_result["dominant_language"]  # always update from detection

    # Model B — extract clinical information
    try:
        session.extraction = model_b.extract(session.transcript)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Extraction failed: {e}")

    return {
        "session_id":             session.id,
        "stage":                  session.stage.value,
        "transcript":             session.transcript,
        "transcript_language":    session.language,
        "transcript_confidence":  session.transcript_conf,
        "language_source":        a_result.get("language_source"),
        "extraction":             session.extraction,
    }