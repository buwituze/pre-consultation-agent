"""
routers/transcription.py — Audio intake endpoint.

POST /sessions/{id}/audio
  → Runs Model A (speech-to-text)
  → Runs Model B (clinical extraction)
  → Returns the first question from Model C
"""

import os
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from typing import Optional

from session import get_session, SessionStage, ConversationTurn
from models import model_a, model_b, model_c

MAX_TURNS = int(os.getenv("MAX_TURNS", 6))

router = APIRouter(prefix="/sessions", tags=["transcription"])


@router.post("/{session_id}/audio")
async def receive_audio(
    session_id: str,
    audio: UploadFile = File(...),
    language: Optional[str] = Form(None),  # override auto-detection if known
):
    """
    Accept a patient audio file, transcribe it, extract clinical information,
    and return the first follow-up question.

    Transitions session: AWAITING_AUDIO → QUESTIONING
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

    # Model C — first question
    first_question = model_c.select_next_question(
        extraction      = session.extraction,
        questions_asked = session.questions_asked,
        patient_answers = session.patient_answers,
    )

    session.stage = SessionStage.QUESTIONING

    return {
        "session_id":          session.id,
        "stage":               session.stage.value,
        "transcript":          session.transcript,
        "transcript_language": session.language,
        "transcript_confidence": session.transcript_conf,
        "extraction":          session.extraction,
        "next_question":       first_question,
    }
