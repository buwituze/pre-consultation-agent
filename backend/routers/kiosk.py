"""
routers/kiosk.py — Patient kiosk interface endpoints.

These are the endpoints the kiosk frontend calls directly.
They wrap the pipeline routers with kiosk-specific concerns:
 - returning TTS-ready text
 - routing decisions
 - simple polling for session stage
 - accepting audio inputs (voice interface)

POST /kiosk/start              → start session, get session_id
POST /kiosk/{id}/audio         → submit initial audio complaint, get first question back
POST /kiosk/{id}/answer        → submit audio answer, get next question or "done"
POST /kiosk/{id}/finish        → trigger scoring, get patient message + routing
GET  /kiosk/{id}/status        → poll current stage (for frontend state machine)

Note: All patient inputs are AUDIO (voice-based kiosk interface).
Each answer is transcribed using Model A before processing.
"""

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from typing import Optional

from session import get_session, SessionStage, ConversationTurn
from routing import assign_routing
from models import model_a, model_b, model_c, model_d, model_e, model_f
import os

MAX_TURNS = int(os.getenv("MAX_TURNS", 6))

router = APIRouter(prefix="/kiosk", tags=["kiosk"])


# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------

class StartRequest(BaseModel):
    language:    str           = "english"
    patient_age: Optional[int] = None


class StartResponse(BaseModel):
    session_id:    str
    greeting:      str        # TTS-ready welcome message


class QuestionResponse(BaseModel):
    session_id:        str
    question:          str    # TTS-ready question text
    coverage_complete: bool


class FinishResponse(BaseModel):
    session_id:    str
    patient_message: str      # TTS-ready guidance message
    department:    str
    queue:         str
    queue_number:  int
    location_hint: str
    urgency_label: str


class StatusResponse(BaseModel):
    session_id: str
    stage:      str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _greeting(language: str) -> str:
    if language == "kinyarwanda":
        return "Murakaza neza. Ndabifurije kuvuga indwara yanyu. Twatangira?"
    return "Welcome. I will ask you a few questions about your symptoms. Ready to begin?"


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/start", response_model=StartResponse)
def kiosk_start(body: StartRequest):
    """Start a new patient session from the kiosk."""
    from session import create_session
    session = create_session(language=body.language, patient_age=body.patient_age)
    return StartResponse(
        session_id = session.id,
        greeting   = _greeting(session.language),
    )


@router.post("/{session_id}/audio", response_model=QuestionResponse)
async def kiosk_audio(
    session_id: str,
    audio: UploadFile = File(...),
    language: Optional[str] = Form(None),
):
    """
    Receive patient's initial audio complaint, transcribe it, extract clinical info,
    and return the first follow-up question.
    
    This is a convenience wrapper that combines:
    - POST /sessions/{id}/audio (Models A + B: transcription + extraction)
    - GET /sessions/{id}/question (Model C: first question)
    
    For kiosk simplicity, all three models run in one call.
    """
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")
    if session.stage != SessionStage.AWAITING_AUDIO:
        raise HTTPException(status_code=409, detail="Audio already submitted for this session.")

    audio_bytes = await audio.read()

    # Model A — transcribe
    try:
        a_result = model_a.transcribe(audio_bytes, language=language or session.language)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Transcription error: {e}")

    session.transcript      = a_result["full_text"]
    session.transcript_conf = a_result["mean_confidence"]
    session.language        = language or a_result["dominant_language"]

    # Model B — extract clinical information
    try:
        session.extraction = model_b.extract(session.transcript)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Extraction error: {e}")

    # Model C — get first question
    question = model_c.select_next_question(
        extraction      = session.extraction,
        questions_asked = session.questions_asked,
        patient_answers = session.patient_answers,
    )
    session.stage = SessionStage.QUESTIONING

    return QuestionResponse(
        session_id        = session.id,
        question          = question,
        coverage_complete = False,
    )


@router.post("/{session_id}/answer", response_model=QuestionResponse)
async def kiosk_answer(
    session_id: str, 
    question: str = Form(...), 
    audio: UploadFile = File(...)
):
    """
    Submit a patient's audio answer. Transcribes it and returns the next question, or signals done.

    The frontend should:
    - If coverage_complete is False: speak the next question via TTS
    - If coverage_complete is True: call POST /kiosk/{id}/finish
    """
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")
    if session.stage != SessionStage.QUESTIONING:
        raise HTTPException(status_code=409, detail="Session is not in the questioning stage.")

    # Read audio file
    audio_bytes = await audio.read()
    
    # Model A — transcribe the answer
    try:
        a_result = model_a.transcribe(audio_bytes, language=session.language)
        answer = a_result["full_text"]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Answer transcription failed: {e}")

    # Record this turn
    session.turns.append(ConversationTurn(question=question, answer=answer))

    # Model B — update extraction
    combined = session.transcript + " " + " ".join(session.patient_answers)
    try:
        session.extraction = model_b.extract(combined)
    except Exception:
        pass

    # Model C — check coverage and get next question
    if model_c.is_coverage_complete(session.extraction, len(session.turns), MAX_TURNS):
        session.stage = SessionStage.SCORING
        return QuestionResponse(session_id=session.id, question="", coverage_complete=True)

    next_q = model_c.select_next_question(
        extraction      = session.extraction,
        questions_asked = session.questions_asked,
        patient_answers = session.patient_answers,
    )
    return QuestionResponse(session_id=session.id, question=next_q, coverage_complete=False)


@router.post("/{session_id}/finish", response_model=FinishResponse)
def kiosk_finish(session_id: str):
    """
    Finalise the session. Runs Models D, E, F and returns
    the patient message and routing decision.
    """
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")
    if session.stage != SessionStage.SCORING:
        raise HTTPException(status_code=409, detail="Session is not ready to finish.")

    session.score = model_d.score(session.extraction, age=session.patient_age)

    routing = assign_routing(
        priority        = session.score["priority"],
        suspected_issue = session.score["suspected_issue"],
    )

    session.patient_message = model_e.generate_message(
        extraction     = session.extraction,
        score          = session.score,
        language       = session.language,
        location       = routing.location_hint,
        low_confidence = session.score.get("confidence", 1.0) < 0.4,
    )

    session.doctor_brief = model_f.generate_brief(
        session_id      = session.id,
        extraction      = session.extraction,
        score           = session.score,
        questions_asked = session.questions_asked,
        patient_answers = session.patient_answers,
        transcript      = session.transcript,
        language        = session.language,
        patient_age     = session.patient_age,
    )
    session.location = routing.location_hint
    session.stage    = SessionStage.COMPLETE

    return FinishResponse(
        session_id      = session.id,
        patient_message = session.patient_message,
        department      = routing.department,
        queue           = routing.queue,
        queue_number    = routing.queue_number,
        location_hint   = routing.location_hint,
        urgency_label   = routing.urgency_label,
    )


@router.get("/{session_id}/status", response_model=StatusResponse)
def kiosk_status(session_id: str):
    """Poll the current stage of a session (for kiosk frontend state machine)."""
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")
    return StatusResponse(session_id=session.id, stage=session.stage.value)
