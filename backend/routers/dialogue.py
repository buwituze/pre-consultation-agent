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
  → Runs Model A to transcribe
  → Records answer and updates extraction
  → Returns next question OR signals that coverage is complete
"""

import os
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel

from session import get_session, SessionStage, ConversationTurn
from models import model_a, model_b, model_c

MAX_TURNS = int(os.getenv("MAX_TURNS", 6))

router = APIRouter(prefix="/sessions", tags=["dialogue"])


class AnswerRequest(BaseModel):
    question: str   # The question that was asked (for the log)
    answer:   str   # The patient's answer (transcribed text from Model A)


@router.get("/{session_id}/question")
def get_next_question(session_id: str):
    """
    Get the next question based on current extraction.
    This is the unified endpoint for all Model C question generation.
    
    Can be called:
    - After initial audio transcription to start dialogue
    - After each answer to continue dialogue
    
    Transitions session: AWAITING_AUDIO → QUESTIONING (first call)
                        QUESTIONING → QUESTIONING (subsequent calls)
    """
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")
    
    # Allow this to be called from AWAITING_AUDIO (first question) or QUESTIONING (subsequent)
    if session.stage not in [SessionStage.AWAITING_AUDIO, SessionStage.QUESTIONING]:
        raise HTTPException(
            status_code=409, 
            detail=f"Cannot get question in stage '{session.stage.value}'. Must be AWAITING_AUDIO or QUESTIONING."
        )
    
    if not session.extraction:
        raise HTTPException(
            status_code=409,
            detail="No extraction available yet. Please submit audio first via /sessions/{id}/audio"
        )
    
    # Check if coverage is already complete
    coverage_done = model_c.is_coverage_complete(
        extraction = session.extraction,
        num_turns  = len(session.turns),
        max_turns  = MAX_TURNS,
    )
    
    if coverage_done:
        session.stage = SessionStage.SCORING
        return {
            "session_id":        session.id,
            "stage":             session.stage.value,
            "coverage_complete": True,
            "next_question":     None,
            "extraction":        session.extraction,
        }
    
    # Model C — select next question
    next_question = model_c.select_next_question(
        extraction      = session.extraction,
        questions_asked = session.questions_asked,
        patient_answers = session.patient_answers,
    )
    
    # Transition to QUESTIONING state
    session.stage = SessionStage.QUESTIONING
    
    return {
        "session_id":        session.id,
        "stage":             session.stage.value,
        "coverage_complete": False,
        "next_question":     next_question,
        "extraction":        session.extraction,
    }


@router.post("/{session_id}/answer")
def submit_answer(session_id: str, body: AnswerRequest):
    """
    Record a patient's answer, update clinical extraction, and return the next question.
    When coverage is complete, returns coverage_complete=True instead of a next question.

    Transitions session: QUESTIONING → QUESTIONING (loop) or QUESTIONING → SCORING (when done)
    """
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")
    if session.stage != SessionStage.QUESTIONING:
        raise HTTPException(status_code=409, detail=f"Session is in stage '{session.stage.value}', not questioning.")

    # Record this turn
    session.turns.append(ConversationTurn(question=body.question, answer=body.answer))

    # Update extraction by re-running Model B on the full transcript + all answers so far
    combined_text = session.transcript + " " + " ".join(session.patient_answers)
    try:
        session.extraction = model_b.extract(combined_text)
    except Exception:
        pass  # Keep existing extraction if update fails

    # Check if we have enough information
    coverage_done = model_c.is_coverage_complete(
        extraction = session.extraction,
        num_turns  = len(session.turns),
        max_turns  = MAX_TURNS,
    )

    if coverage_done:
        session.stage = SessionStage.SCORING
        return {
            "session_id":        session.id,
            "stage":             session.stage.value,
            "coverage_complete": True,
            "next_question":     None,
            "extraction":        session.extraction,
        }

    # Select and return the next question
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
    question: str = Form(...),
    audio: UploadFile = File(...),
):
    """
    Accept a patient's audio answer to a question, transcribe it, update extraction,
    and return the next question. This is for voice-based interactions.
    
    Workflow:
    1. Run Model A to transcribe audio answer
    2. Record the answer
    3. Update extraction with Model B
    4. Get next question with Model C (or signal completion)

    Transitions session: QUESTIONING → QUESTIONING (loop) or QUESTIONING → SCORING (when done)
    """
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")
    if session.stage != SessionStage.QUESTIONING:
        raise HTTPException(status_code=409, detail=f"Session is in stage '{session.stage.value}', not questioning.")

    # Read audio file
    audio_bytes = await audio.read()
    
    # Model A — transcribe the answer
    try:
        a_result = model_a.transcribe(audio_bytes, language=session.language)
        answer_text = a_result["full_text"]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Answer transcription failed: {e}")

    # Record this turn
    session.turns.append(ConversationTurn(question=question, answer=answer_text))

    # Model B — update extraction with new information
    combined_text = session.transcript + " " + " ".join(session.patient_answers)
    try:
        session.extraction = model_b.extract(combined_text)
    except Exception:
        pass  # Keep existing extraction if update fails

    # Model C — check if coverage is complete
    coverage_done = model_c.is_coverage_complete(
        extraction = session.extraction,
        num_turns  = len(session.turns),
        max_turns  = MAX_TURNS,
    )

    if coverage_done:
        session.stage = SessionStage.SCORING
        return {
            "session_id":        session.id,
            "stage":             session.stage.value,
            "coverage_complete": True,
            "next_question":     None,
            "extraction":        session.extraction,
            "transcribed_answer": answer_text,
        }

    # Model C — select next question
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
        "transcribed_answer": answer_text,
    }
