"""
routers/sessions.py — Session lifecycle endpoints.

POST /sessions        → start a new patient session
DELETE /sessions/{id} → end and clean up a session
GET  /sessions/{id}   → inspect current session state (useful for debugging)
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from session import create_session, get_session, delete_session

router = APIRouter(prefix="/sessions", tags=["sessions"])


class StartSessionRequest(BaseModel):
    language:    Optional[str] = None   # Patient's screen selection, or None if skipped.
                                        # Passed as a hint to Model A — detection always runs.
    patient_age: Optional[int] = None
    location:    str           = ""     # e.g. "Emergency, Desk 3"


class StartSessionResponse(BaseModel):
    session_id: str
    stage:      str


@router.post("", response_model=StartSessionResponse)
def start_session(body: StartSessionRequest):
    """Create a new patient session and return its ID."""
    session = create_session(
        language    = body.language or "unknown",
        patient_age = body.patient_age,
        location    = body.location,
    )
    return StartSessionResponse(session_id=session.id, stage=session.stage.value)


@router.get("/{session_id}")
def get_session_state(session_id: str):
    """Return the current state of a session (for debugging / frontend polling)."""
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")
    return {
        "session_id":      session.id,
        "stage":           session.stage.value,
        "language":        session.language,
        "patient_age":     session.patient_age,
        "location":        session.location,
        "transcript":      session.transcript,
        "extraction":      session.extraction,
        "turns":           [{"question": t.question, "answer": t.answer} for t in session.turns],
        "score":           session.score,
        "patient_message": session.patient_message,
        "doctor_brief":    session.doctor_brief,
    }


@router.delete("/{session_id}")
def end_session(session_id: str):
    """Delete a session and free its memory."""
    if not get_session(session_id):
        raise HTTPException(status_code=404, detail="Session not found.")
    delete_session(session_id)
    return {"deleted": session_id}