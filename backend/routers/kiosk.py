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
only WAV format is supported. See backend/AUDIO_FORMAT.md for details.
    Frontend apps should record audio in WAV format (16kHz mono recommended).
    
Data persistence:
    Sessions live in memory during conversation for speed.
    Audio files and all data are persisted to database only when session completes.
"""

import os
import asyncio
import uuid
from pathlib import Path
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Body
from pydantic import BaseModel
from typing import Optional

from session import get_session, create_session, SessionStage, ConversationTurn
from routing import assign_routing
from models import model_a, model_b, model_c, model_d, model_e, model_f
from database.database import (
    PatientDB, SessionDB, ConversationDB, SymptomDB, PredictionDB,
    AudioDB, QueueDB, ExtendedSessionDB, DatabaseConnection
)

# Initialize database connection pool
try:
    DatabaseConnection.initialize_pool()
except:
    pass  # May already be initialized

# Audio storage directory
AUDIO_DIR = Path(os.getenv("AUDIO_STORAGE_DIR", "data/audio"))
AUDIO_DIR.mkdir(parents=True, exist_ok=True)

MAX_TURNS = int(os.getenv("MAX_TURNS", 6))

router = APIRouter(prefix="/kiosk", tags=["kiosk"])


# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------

class StartRequest(BaseModel):
    language:    Optional[str] = None    # Patient's selection, or None if skipped
    patient_age: Optional[int] = None
    patient_location: Optional[str] = None
    facility_id: int = 1                  # Default facility


class StartResponse(BaseModel):
    session_id: str
    greeting:   str


class QuestionResponse(BaseModel):
    session_id:        str
    question:          str
    coverage_complete: bool
    patient_name:      str = ""
    patient_phone:     str = ""


class FinishRequest(BaseModel):
    patient_name:      str = ""
    patient_phone:     str = ""
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


def _save_audio_file(session_id: str, audio_bytes: bytes, sequence: int, speaker: str) -> str:
    """Save audio file to disk and return file path"""
    session_dir = AUDIO_DIR / session_id
    session_dir.mkdir(exist_ok=True)
    
    filename = f"{sequence:03d}_{speaker}.wav"
    file_path = session_dir / filename
    
    with open(file_path, 'wb') as f:
        f.write(audio_bytes)
    
    return str(file_path)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/start", response_model=StartResponse)
def kiosk_start(body: StartRequest):
    """
    Start a new patient session.
    language is the patient's screen selection — optional, used as a hint only.
    Creates patient record and session record in database.
    
    Returns:
        StartResponse with session_id and greeting
        
    Raises:
        503 if database is not ready
        500 if database operation fails
    """
    print("\n" + "="*80)
    print("🚀 NEW SESSION STARTED")
    print(f"Language selected: {body.language}")
    print(f"Patient Age: {body.patient_age}")
    print(f"Facility ID: {body.facility_id}")
    
    # Normalize language to lowercase for consistency
    normalized_language = body.language.lower() if body.language else "unknown"
    
    try:
        # Create or get patient in database
        patient = PatientDB.create_new_patient(
            preferred_language=normalized_language if normalized_language != "unknown" else "kinyarwanda",
            location=body.patient_location
        )
        print(f"Patient DB ID: {patient['patient_id']}")
        
        # Create session in database
        db_session = SessionDB.create_session(patient['patient_id'])
        print(f"Session DB ID: {db_session['session_id']}")
        
    except Exception as e:
        error_msg = f"Database operation failed: {type(e).__name__}: {str(e)}"
        print(f"❌ {error_msg}")
        import traceback
        traceback.print_exc()
        
        # Check if it's a connection error
        if "connection" in str(e).lower() or "pool" in str(e).lower():
            raise HTTPException(
                status_code=503,
                detail="Database not available. Check server startup at /startup/status"
            )
        else:
            raise HTTPException(status_code=500, detail=error_msg)
    
    # Create in-memory session (for fast conversation)
    session = create_session(
        language    = normalized_language,
        patient_age = body.patient_age,
    )
    # Store DB IDs in memory session for later
    session.db_session_id = db_session['session_id']
    session.db_patient_id = patient['patient_id']
    session.facility_id = body.facility_id
    
    greeting = _greeting(normalized_language)
    
    print(f"In-Memory Session ID: {session.id}")
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
    
    Audio is saved to disk but not yet persisted to database (happens on finish).
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
    
    # Save audio file to disk
    audio_path = _save_audio_file(session_id, audio_bytes, 0, "patient")
    session.audio_files = [(0, "patient", audio_path, len(audio_bytes))]
    print(f"Audio saved to: {audio_path}")

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
        patient_name      = session.patient_name,
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
    
    Audio saved to disk but not persisted to database yet.
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
    
    # Save audio file to disk
    if not hasattr(session, 'audio_files'):
        session.audio_files = []
    sequence = len(session.audio_files)
    audio_path = _save_audio_file(session_id, audio_bytes, sequence, "patient")
    session.audio_files.append((sequence, "patient", audio_path, len(audio_bytes)))
    print(f"Audio saved to: {audio_path}")

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
        return QuestionResponse(session_id=session.id, question="", coverage_complete=True, patient_name=session.patient_name)

    print(f"📊 Coverage not yet complete ({len(session.turns)}/{MAX_TURNS} turns)")
    next_q = model_c.select_next_question(
        extraction      = session.extraction,
        questions_asked = session.questions_asked,
        patient_answers = session.patient_answers,
    )
    print(f"✅ Next question generated!")
    print(f"💬 ASSISTANT ASKS: '{next_q}'")
    print("="*80 + "\n")
    return QuestionResponse(session_id=session.id, question=next_q, coverage_complete=False, patient_name=session.patient_name)


@router.post("/{session_id}/finish", response_model=FinishResponse)
async def kiosk_finish(
    session_id: str,
    body: Optional[FinishRequest] = Body(default=None),
):
    """
    Finalise the session. Runs Models D, E, F and returns
    the patient message and routing decision.
    
    Persists all session data to database:
    - Audio file references
    - Conversation messages
    - Extracted symptoms
    - Risk prediction
    - Complete session data
    - Creates queue entry
    """
    print("\n" + "="*80)
    print("🏁 FINISHING SESSION")
    print(f"Session ID: {session_id}")
    
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")
    if session.stage != SessionStage.SCORING:
        raise HTTPException(status_code=409, detail="Session is not ready to finish.")
    body = body or FinishRequest()

    print("\n🔄 Running Model D (Risk Scoring)...")
    session.score = await asyncio.to_thread(model_d.score, session.extraction, age=session.patient_age)
    print(f"✅ Score: {session.score}")

    print("\n🔄 Assigning routing...")
    routing = assign_routing(
        priority        = session.score["priority"],
        suspected_issue = session.score["suspected_issue"],
    )
    print(f"✅ Routing: {routing.department}, Queue: {routing.queue}")

    print("\n🔄 Running Model E (Patient Message)...")
    session.patient_message = await asyncio.to_thread(
        model_e.generate_message,
        extraction     = session.extraction,
        score          = session.score,
        language       = session.language,
        location       = routing.location_hint,
        low_confidence = session.score.get("confidence", 1.0) < 0.4,
    )
    print(f"✅ Patient message generated")

    print("\n🔄 Running Model F (Doctor Brief)...")
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
    print(f"✅ Doctor brief generated")
    
    session.location = routing.location_hint
    session.stage    = SessionStage.COMPLETE

    # ========================================================================
    # PERSIST TO DATABASE
    # ========================================================================
    print("\n💾 PERSISTING TO DATABASE...")

    # Keep a safe default so finish can still respond if DB persistence fails.
    queue_entry = {"queue_number": 0}

    try:
        # 0. Update patient info (use placeholders if empty — DB requires name length >= 2, valid phone)
        full_name = (body.patient_name or session.patient_name or "").strip()
        phone_number = (body.patient_phone or "").strip()
        if len(full_name) < 2:
            full_name = "Unknown"
        if not phone_number or not all(c in "0123456789+-() " for c in phone_number):
            phone_number = "0"
        PatientDB.update_patient(
            patient_id=session.db_patient_id,
            full_name=full_name,
            phone_number=phone_number,
        )
        print(f"✅ Updated patient info")
        # 1. Save audio file references
        if hasattr(session, 'audio_files'):
            for seq, speaker, path, size in session.audio_files:
                AudioDB.save_audio_reference(
                    session_id=session.db_session_id,
                    sequence_number=seq,
                    speaker_type=speaker,
                    file_path=path,
                    file_size_bytes=size
                )
            print(f"✅ Saved {len(session.audio_files)} audio references")
        
        # 2. Save conversation messages
        seq_num = 1
        # Initial patient complaint
        ConversationDB.add_message(
            session_id=session.db_session_id,
            sender_type='patient',
            message_text=session.transcript,
            sequence_number=seq_num
        )
        seq_num += 1
        
        # Q&A turns
        for turn in session.turns:
            ConversationDB.add_message(
                session_id=session.db_session_id,
                sender_type='ml_system',
                message_text=turn.question,
                sequence_number=seq_num
            )
            seq_num += 1
            ConversationDB.add_message(
                session_id=session.db_session_id,
                sender_type='patient',
                message_text=turn.answer,
                sequence_number=seq_num
            )
            seq_num += 1
        print(f"✅ Saved {seq_num - 1} conversation messages")
        
        # 3. Save symptoms
        if session.extraction.get('symptoms'):
            for symptom in session.extraction['symptoms']:
                if isinstance(symptom, dict):
                    SymptomDB.add_symptom(
                        session_id=session.db_session_id,
                        symptom_name=symptom.get('name', 'unknown'),
                        severity=symptom.get('severity'),
                        duration=symptom.get('duration'),
                        additional_info=symptom.get('description')
                    )
                else:
                    # Simple string symptom
                    SymptomDB.add_symptom(
                        session_id=session.db_session_id,
                        symptom_name=str(symptom)
                    )
            print(f"✅ Saved {len(session.extraction['symptoms'])} symptoms")
        
        # 4. Save prediction/risk score
        db_risk_level = str(session.score.get('priority', 'medium')).strip().lower()
        if db_risk_level not in {'low', 'medium', 'high'}:
            db_risk_level = 'medium'
        PredictionDB.create_prediction(
            session_id=session.db_session_id,
            predicted_condition=session.score.get('suspected_issue', 'Unknown'),
            risk_level=db_risk_level,
            confidence_score=session.score.get('confidence', 0.5),
            model_version='1.0'
        )
        print(f"✅ Saved prediction")
        
        # 5. Save complete session data
        ExtendedSessionDB.save_complete_session(
            session_id=session.db_session_id,
            extraction_data=session.extraction,
            score_data=session.score,
            patient_message=session.patient_message,
            doctor_brief=session.doctor_brief,
            full_transcript=session.transcript,
            transcript_confidence=session.transcript_conf,
            detected_language=session.language
        )
        print(f"✅ Saved complete session data")
        
        # 6. Create queue entry
        queue_entry = QueueDB.create_queue_entry(
            session_id=session.db_session_id,
            patient_id=session.db_patient_id,
            facility_id=session.facility_id
        )
        print(f"✅ Created queue entry #{queue_entry['queue_number']}")
        
        print("💾 DATABASE PERSISTENCE COMPLETE")
        
    except Exception as e:
        print(f"❌ Database persistence error: {e}")
        import traceback
        traceback.print_exc()
        # Don't fail the request - data is in memory, can be retried
        # In production, you'd want better error handling here
    
    print("="*80 + "\n")

    return FinishResponse(
        session_id      = session.id,
        patient_message = session.patient_message,
        department      = routing.department,
        queue           = routing.queue,
        queue_number    = queue_entry.get('queue_number', 0),
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
