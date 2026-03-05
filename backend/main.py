"""
main.py — FastAPI application entry point.

Run with:
    uvicorn main:app --reload --port 8000

Interactive docs: http://localhost:8000/docs
"""

from dotenv import load_dotenv
load_dotenv()

import asyncio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from models import model_a
from routers import sessions, transcription, dialogue, triage, kiosk, doctor
from routers import auth, facilities, rooms, queue, patients
from database.database import DatabaseConnection


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize database connection pool
    print("🔌 Initializing database connection pool...")
    try:
        DatabaseConnection.initialize_pool()
        print("✅ Database connected")
    except Exception as e:
        print(f"⚠️ Database connection failed: {e}")
    
    # Load Whisper models in background — this takes ~1-2 min on first run
    # Server will start immediately, models load asynchronously
    print("🚀 Server starting... Models will load in background")
    asyncio.create_task(asyncio.to_thread(model_a.load_models))
    
    yield
    
    # Cleanup on shutdown
    print("🔌 Closing database connection pool...")
    DatabaseConnection.close_pool()
    print("✅ Shutdown complete")


app = FastAPI(
    title="Hospital Pre-Consultation API",
    description="Voice-based triage pipeline for Kinyarwanda and English patients.",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware for Flutter web app
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins like ["http://localhost:PORT"]
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Authentication
app.include_router(auth.router)

# Internal pipeline — model-to-model orchestration
app.include_router(sessions.router)
app.include_router(transcription.router)
app.include_router(dialogue.router)
app.include_router(triage.router)

# Interface-facing — kiosk and clinician dashboard
app.include_router(kiosk.router)
app.include_router(doctor.router)

# Management APIs — facilities, rooms, queue, patients
app.include_router(facilities.router)
app.include_router(rooms.router)
app.include_router(queue.router)
app.include_router(patients.router)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/models/status")
def models_status():
    """Check if AI models are loaded and ready."""
    return model_a.get_models_status()
