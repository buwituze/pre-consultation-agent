"""
routers/dialogue.py — Model C question-answer loop endpoints.

GET  /sessions/{id}/question
  → Runs Model C to get next question based on current extraction
  → Transitions session to QUESTIONING stage

POST /sessions/{id}/answer
  → Records patient's answer (text)
  → Re-runs Model B to update extraction with new info
  → Returns next question OR signals that coverage is complete

POST /sessions/{id}/answer-audio
  → Accepts audio answer from patient
  → Runs Model A to transcribe (using session language as hint)
  → Records answer and updates extraction
  → Returns next question OR signals that coverage is complete

Note: /answer and /answer-audio are internal/debug routes.
      The kiosk frontend uses POST /kiosk/{id}/answer which handles
      audio answers directly in one call.
"""

import os
import asyncio
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel

from session import get_session, SessionStage, ConversationTurn
from models import model_a, model_b, model_c

MAX_TURNS = int(os.getenv("MAX_TURNS", 6))

router = APIRouter(prefix="/sessions", tags=["dialogue"])


class AnswerRequest(BaseModel):
    question: str   # The question that was asked (for the log)
    answer:   str   # The patient's answer (pre-transcribed text)


@router.get("/{session_id}/question")
def get_next_question(session_id: str):
    """
    Get the next question based on current extraction.

    Can be called:
    - After initial audio transcription to start dialogue
    - After each answer to continue dialogue

    Transitions session: AWAITING_AUDIO → QUESTIONING (first call)
                         QUESTIONING    → QUESTIONING (subsequent calls)
    """
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")
    if session.stage not in (SessionStage.AWAITING_AUDIO, SessionStage.QUESTIONING):
        raise HTTPException(
            status_code=409,
            detail=f"Cannot get question in stage '{session.stage.value}'. Must be AWAITING_AUDIO or QUESTIONING.",
        )
    if not session.extraction:
        raise HTTPException(
            status_code=409,
            detail="No extraction available yet. Submit audio first via POST /sessions/{id}/audio.",
        )

    if model_c.is_coverage_complete(session.extraction, len(session.turns), MAX_TURNS):
        session.stage = SessionStage.SCORING
        return {
            "session_id":        session.id,
            "stage":             session.stage.value,
            "coverage_complete": True,
            "next_question":     None,
            "extraction":        session.extraction,
        }

    next_question = model_c.select_next_question(
        extraction      = session.extraction,
        questions_asked = session.questions_asked,
        patient_answers = session.patient_answers,
    )
    session.stage = SessionStage.QUESTIONING

    return {
        "session_id":        session.id,
        "stage":             session.stage.value,
        "coverage_complete": False,
        "next_question":     next_question,
        "extraction":        session.extraction,
    }


@router.post("/{session_id}/answer")
async def submit_answer(session_id: str, body: AnswerRequest):
    """
    Record a pre-transcribed patient answer and return the next question.
    For audio answers use POST /sessions/{id}/answer-audio instead.

    Transitions session: QUESTIONING → QUESTIONING (loop) or → SCORING (when done)
    """
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")
    if session.stage != SessionStage.QUESTIONING:
        raise HTTPException(
            status_code=409,
            detail=f"Session is in stage '{session.stage.value}', not questioning.",
        )

    session.turns.append(ConversationTurn(question=body.question, answer=body.answer))

    combined = session.transcript + " " + " ".join(session.patient_answers)
    try:
        session.extraction = await asyncio.to_thread(model_b.extract, combined)
    except Exception:
        pass

    if model_c.is_coverage_complete(session.extraction, len(session.turns), MAX_TURNS):
        session.stage = SessionStage.SCORING
        return {
            "session_id":        session.id,
            "stage":             session.stage.value,
            "coverage_complete": True,
            "next_question":     None,
            "extraction":        session.extraction,
        }

    next_question = model_c.select_next_question(
        extraction      = session.extraction,
        questions_asked = session.questions_asked,
        patient_answers = session.patient_answers,
    )

    return {
        "session_id":        session.id,
        "stage":             session.stage.value,
        "coverage_complete": False,
        "next_question":     next_question,
        "extraction":        session.extraction,
    }


@router.post("/{session_id}/answer-audio")
async def submit_answer_audio(
    session_id: str,
    question:   str        = Form(...),
    audio:      UploadFile = File(...),
):
    """
    Accept a patient's audio answer, transcribe it, update extraction,
    and return the next question.

    Uses the session's already-detected language as a hint to Model A.
    Detection still runs on every call — the hint is only a tiebreaker.

    Transitions session: QUESTIONING → QUESTIONING (loop) or → SCORING (when done)
    """
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")
    if session.stage != SessionStage.QUESTIONING:
        raise HTTPException(
            status_code=409,
            detail=f"Session is in stage '{session.stage.value}', not questioning.",
        )

    audio_bytes = await audio.read()

    # Use the session's detected language as hint — detection still runs
    hint = session.language if session.language != "unknown" else None

    try:
        a_result    = await asyncio.to_thread(model_a.transcribe, audio_bytes, language_hint=hint)
        answer_text = a_result["full_text"]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Answer transcription failed: {e}")

    session.turns.append(ConversationTurn(question=question, answer=answer_text))

    combined = session.transcript + " " + " ".join(session.patient_answers)
    try:
        session.extraction = await asyncio.to_thread(model_b.extract, combined)
    except Exception:
        pass

    if model_c.is_coverage_complete(session.extraction, len(session.turns), MAX_TURNS):
        session.stage = SessionStage.SCORING
        return {
            "session_id":         session.id,
            "stage":              session.stage.value,
            "coverage_complete":  True,
            "next_question":      None,
            "extraction":         session.extraction,
            "transcribed_answer": answer_text,
        }

    next_question = model_c.select_next_question(
        extraction      = session.extraction,
        questions_asked = session.questions_asked,
        patient_answers = session.patient_answers,
    )

    return {
        "session_id":         session.id,
        "stage":              session.stage.value,
        "coverage_complete":  False,
        "next_question":      next_question,
        "extraction":         session.extraction,
        "transcribed_answer": answer_text,
    }