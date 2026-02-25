"""
routers/dialogue.py — Model C question-answer loop endpoint.

POST /sessions/{id}/answer
  → Records patient's answer
  → Re-runs Model B to update extraction with new info
  → Returns next question OR signals that coverage is complete
"""

import os
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from session import get_session, SessionStage, ConversationTurn
from models import model_b, model_c

MAX_TURNS = int(os.getenv("MAX_TURNS", 6))

router = APIRouter(prefix="/sessions", tags=["dialogue"])


class AnswerRequest(BaseModel):
    question: str   # The question that was asked (for the log)
    answer:   str   # The patient's answer (transcribed text from Model A)


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
