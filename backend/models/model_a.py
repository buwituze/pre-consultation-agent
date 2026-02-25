"""
models/model_a.py — Speech-to-text wrapper.

Loads Whisper models once at startup and exposes a single transcribe() function.
"""

import os
import numpy as np
import librosa
import torch
from transformers import pipeline
from langdetect import detect, LangDetectException
from typing import Optional

SR = 16_000
DEVICE = os.getenv("DEVICE", "cpu")
DTYPE  = torch.float16 if DEVICE == "cuda" else torch.float32
HF_TOKEN = os.getenv("HF_TOKEN")  # Load Hugging Face token from environment

_kin_pipe = None
_eng_pipe = None
_models_ready = False
_loading_status = "not_started"


def load_models():
    """Call once at API startup to load both Whisper models into memory."""
    global _kin_pipe, _eng_pipe, _models_ready, _loading_status
    
    try:
        _loading_status = "loading_kinyarwanda_model"
        _kin_pipe = pipeline(
            "automatic-speech-recognition",
            model="akera/whisper-large-v3-kin-200h-v2",
            torch_dtype=DTYPE,
            device=DEVICE,
            return_timestamps=True,
            token=HF_TOKEN,
        )
        
        _loading_status = "loading_english_model"
        _eng_pipe = pipeline(
            "automatic-speech-recognition",
            model="openai/whisper-large-v3",
            torch_dtype=DTYPE,
            device=DEVICE,
            return_timestamps=True,
            token=HF_TOKEN,
        )
        
        _loading_status = "ready"
        _models_ready = True
        print("✓ All Whisper models loaded successfully")
    except Exception as e:
        _loading_status = f"error: {str(e)}"
        print(f"✗ Error loading models: {e}")


def get_models_status() -> dict:
    """Return the current model loading status."""
    return {
        "ready": _models_ready,
        "status": _loading_status
    }


def _detect_language(audio: np.ndarray) -> str:
    result = _eng_pipe(
        {"array": audio, "sampling_rate": SR},
        generate_kwargs={"task": "transcribe", "language": None},
        return_timestamps=False,
    )
    try:
        code = detect(result.get("text", ""))
        return "kinyarwanda" if code == "rw" else "english"
    except LangDetectException:
        return "kinyarwanda"


def _confidence(chunks: list) -> float:
    if not chunks:
        return 0.0
    bad   = ["[BLANK_AUDIO]", "[MUSIC]"]
    hits  = sum(1 for c in chunks if any(t in c.get("text", "") for t in bad))
    return round(max(0.0, 1.0 - hits / len(chunks)), 3)


def transcribe(audio_bytes: bytes, language: Optional[str] = None) -> dict:
    """
    Transcribe raw audio bytes.

    Args:
        audio_bytes : Raw audio file content (wav / mp3 / flac).
        language    : Force 'english' or 'kinyarwanda'. Auto-detects if None.

    Returns:
        {"full_text": str, "dominant_language": str, "mean_confidence": float}
    """
    if not _models_ready:
        raise RuntimeError(f"Models not ready yet. Status: {_loading_status}")
    
    import io
    audio, _ = librosa.load(io.BytesIO(audio_bytes), sr=SR, mono=True)

    seg_len  = 30 * SR
    segments = []

    for i in range(0, len(audio), seg_len):
        chunk = audio[i : i + seg_len]
        lang  = language or _detect_language(chunk)
        pipe  = _kin_pipe if lang == "kinyarwanda" else _eng_pipe

        gen_kwargs = {"task": "transcribe"}
        if lang == "english":
            gen_kwargs["language"] = "english"

        result = pipe({"array": chunk, "sampling_rate": SR},
                      generate_kwargs=gen_kwargs, return_timestamps=True)
        chunks = result.get("chunks", [])
        segments.append({
            "text":       result.get("text", "").strip(),
            "language":   lang,
            "confidence": _confidence(chunks),
        })

    lang_votes = [s["language"] for s in segments]
    return {
        "full_text":         " ".join(s["text"] for s in segments if s["text"]),
        "dominant_language": max(set(lang_votes), key=lang_votes.count),
        "mean_confidence":   round(float(np.mean([s["confidence"] for s in segments])), 3),
    }
