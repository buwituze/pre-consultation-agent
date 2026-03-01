"""
routers/kiosk.py — Patient kiosk interface endpoints.

POST /kiosk/start              → start session, get session_id + greeting
POST /kiosk/{id}/audio         → submit initial audio complaint, get first question
POST /kiosk/{id}/answer        → submit audio answer, get next question or "done"
POST /kiosk/{id}/finish        → trigger scoring, get patient message + routing
GET  /kiosk/{id}/status        → poll current stage

Language handling:
    The frontend sends the patient's selected language (or None if they skipped).
    Model A always detects language from audio regardless — the selected language
    is passed as a hint and only used as a tiebreaker, never as an override.
    This means a patient who selected English but speaks Kinyarwanda will still
    be correctly transcribed in Kinyarwanda.
AUDIO FORMAT REQUIREMENT:
    Only WAV format is supported. See backend/AUDIO_FORMAT.md for details.
    Frontend apps should record audio in WAV format (16kHz mono recommended)."""

import os
import asyncio
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from typing import Optional

from session import get_session, create_session, SessionStage, ConversationTurn
from routing import assign_routing
from models import model_a, model_b, model_c, model_d, model_e, model_f

MAX_TURNS = int(os.getenv("MAX_TURNS", 6))

router = APIRouter(prefix="/kiosk", tags=["kiosk"])


# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------

class StartRequest(BaseModel):
    language:    Optional[str] = None    # Patient's selection, or None if skipped
    patient_age: Optional[int] = None


class StartResponse(BaseModel):
    session_id: str
    greeting:   str


class QuestionResponse(BaseModel):
    session_id:        str
    question:          str
    coverage_complete: bool


class FinishResponse(BaseModel):
    session_id:      str
    patient_message: str
    department:      str
    queue:           str
    queue_number:    int
    location_hint:   str
    urgency_label:   str


class StatusResponse(BaseModel):
    session_id: str
    stage:      str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _greeting(language: Optional[str]) -> str:
    if language == "kinyarwanda":
        return "Murakaza neza. Ndabifurije kuvuga indwara yanyu. Twatangira?"
    if language == "english":
        return "Welcome. I will ask you a few questions about your symptoms. Ready to begin?"
    # No selection — offer both
    return "Welcome / Murakaza neza. Please speak to begin. / Vuga kugirango utangire."


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/start", response_model=StartResponse)
def kiosk_start(body: StartRequest):
    """
    Start a new patient session.
    language is the patient's screen selection — optional, used as a hint only.
    """
    print("\n" + "="*80)
    print("🚀 NEW SESSION STARTED")
    print(f"Language selected: {body.language}")
    print(f"Patient Age: {body.patient_age}")
    
    # Normalize language to lowercase for consistency
    normalized_language = body.language.lower() if body.language else "unknown"
    
    session = create_session(
        language    = normalized_language,
        patient_age = body.patient_age,
    )
    greeting = _greeting(normalized_language)
    
    print(f"Session ID: {session.id}")
    print(f"💬 Greeting: '{greeting}'")
    print("="*80 + "\n")
    
    return StartResponse(
        session_id = session.id,
        greeting   = greeting,
    )


@router.post("/{session_id}/audio", response_model=QuestionResponse)
async def kiosk_audio(
    session_id: str,
    audio: UploadFile = File(...),
    language: Optional[str] = Form(None),
):
    """
    Receive patient's initial audio complaint, transcribe it, extract clinical
    info, and return the first follow-up question.

    language (form field): the patient's screen selection, passed as a hint to
    Model A. Detection always runs regardless of this value.
    """
    print("\n" + "="*80)
    print("🎤 INITIAL AUDIO RECEIVED")
    print(f"Session ID: {session_id}")
    
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")
    if session.stage != SessionStage.AWAITING_AUDIO:
        raise HTTPException(status_code=409, detail="Audio already submitted for this session.")

    audio_bytes = await audio.read()
    print(f"Audio size: {len(audio_bytes)} bytes")

    # Use session language as hint if not passed directly in the form
    # Normalize language to lowercase for consistency
    hint = language.lower() if language else (session.language if session.language != "unknown" else None)
    print(f"Language hint: {hint}")

    print("\n🔄 Running Model A (Speech-to-Text)...")
    try:
        a_result = await asyncio.to_thread(model_a.transcribe, audio_bytes, language_hint=hint)
        print(f"✅ Transcription successful!")
        print(f"📝 PATIENT SAID: '{a_result['full_text']}'")
        print(f"   Confidence: {a_result['mean_confidence']:.2%}")
        print(f"   Language detected: {a_result['dominant_language']}")
    except KeyboardInterrupt:
        print("❌ Interrupted by user")
        raise
    except Exception as e:
        print(f"❌ Transcription error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Transcription error: {type(e).__name__}: {e}")

    session.transcript      = a_result["full_text"]
    session.transcript_conf = a_result["mean_confidence"]
    session.language        = a_result["dominant_language"]  # always update from detection result

    print("\n🔄 Running Model B (Clinical Extraction)...")
    try:
        session.extraction = await asyncio.to_thread(model_b.extract, session.transcript)
        print(f"✅ Extraction successful!")
        print(f"   Extracted: {session.extraction}")
    except Exception as e:
        print(f"❌ Extraction error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Extraction error: {type(e).__name__}: {e}")

    print("\n🔄 Running Model C (Question Generation)...")
    question = model_c.select_next_question(
        extraction      = session.extraction,
        questions_asked = session.questions_asked,
        patient_answers = session.patient_answers,
    )
    session.stage = SessionStage.QUESTIONING
    print(f"✅ Question generated!")
    print(f"💬 ASSISTANT ASKS: '{question}'")
    print("="*80 + "\n")

    return QuestionResponse(
        session_id        = session.id,
        question          = question,
        coverage_complete = False,
    )


@router.post("/{session_id}/answer", response_model=QuestionResponse)
async def kiosk_answer(
    session_id: str,
    question: str = Form(...),
    audio: UploadFile = File(...),
):
    """
    Submit a patient's audio answer. Transcribes it using the session's
    detected language, then returns the next question or signals done.

    When coverage_complete is True, call POST /kiosk/{id}/finish next.
    """
    print("\n" + "="*80)
    print("🎤 ANSWER AUDIO RECEIVED")
    print(f"Session ID: {session_id}")
    print(f"Previous question: '{question}'")
    
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")
    if session.stage != SessionStage.QUESTIONING:
        raise HTTPException(status_code=409, detail="Session is not in the questioning stage.")

    audio_bytes = await audio.read()
    print(f"Audio size: {len(audio_bytes)} bytes")

    # For answers, use the already-detected session language as the hint
    print(f"\n🔄 Running Model A (Transcribing answer in {session.language})...")
    try:
        a_result = await asyncio.to_thread(model_a.transcribe, audio_bytes, language_hint=session.language)
        answer   = a_result["full_text"]
        print(f"✅ Transcription successful!")
        print(f"📝 PATIENT ANSWERED: '{answer}'")
        print(f"   Confidence: {a_result['mean_confidence']:.2%}")
    except Exception as e:
        print(f"❌ Answer transcription failed: {e}")
        raise HTTPException(status_code=500, detail=f"Answer transcription failed: {e}")

    session.turns.append(ConversationTurn(question=question, answer=answer))
    print(f"Turn #{len(session.turns)} recorded")

    print("\n🔄 Running Model B (Updating extraction)...")
    combined = session.transcript + " " + " ".join(session.patient_answers)
    try:
        session.extraction = await asyncio.to_thread(model_b.extract, combined)
        print(f"✅ Extraction updated: {session.extraction}")
    except Exception as e:
        print(f"⚠️ Extraction update failed (continuing): {e}")

    print("\n🔄 Running Model C (Checking coverage)...")
    if model_c.is_coverage_complete(session.extraction, len(session.turns), MAX_TURNS):
        session.stage = SessionStage.SCORING
        print(f"✅ Coverage complete! ({len(session.turns)} turns completed)")
        print("="*80 + "\n")
        return QuestionResponse(session_id=session.id, question="", coverage_complete=True)

    print(f"📊 Coverage not yet complete ({len(session.turns)}/{MAX_TURNS} turns)")
    next_q = model_c.select_next_question(
        extraction      = session.extraction,
        questions_asked = session.questions_asked,
        patient_answers = session.patient_answers,
    )
    print(f"✅ Next question generated!")
    print(f"💬 ASSISTANT ASKS: '{next_q}'")
    print("="*80 + "\n")
    return QuestionResponse(session_id=session.id, question=next_q, coverage_complete=False)


@router.post("/{session_id}/finish", response_model=FinishResponse)
async def kiosk_finish(session_id: str):
    """
    Finalise the session. Runs Models D, E, F and returns
    the patient message and routing decision.
    """
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")
    if session.stage != SessionStage.SCORING:
        raise HTTPException(status_code=409, detail="Session is not ready to finish.")

    session.score = await asyncio.to_thread(model_d.score, session.extraction, age=session.patient_age)

    routing = assign_routing(
        priority        = session.score["priority"],
        suspected_issue = session.score["suspected_issue"],
    )

    session.patient_message = await asyncio.to_thread(
        model_e.generate_message,
        extraction     = session.extraction,
        score          = session.score,
        language       = session.language,
        location       = routing.location_hint,
        low_confidence = session.score.get("confidence", 1.0) < 0.4,
    )

    session.doctor_brief = await asyncio.to_thread(
        model_f.generate_brief,
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
    """Poll the current stage of a session."""
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")
    return StatusResponse(session_id=session.id, stage=session.stage.value)
