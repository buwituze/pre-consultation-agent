"""
models/model_a.py — Speech-to-text wrapper.

Language handling:
    Whisper always detects the language from audio features on every call.
    If the patient selected a language on the kiosk screen, it is passed as a
    hint and used as a tiebreaker when detection confidence is low. Detection
    is never skipped — the selected language never overrides what Whisper hears.

    After fine-tuning on patient audio data, detection becomes highly reliable
    and the hint matters less. No changes to this file will be needed at that
    point — just swap the model ID in load_models().
"""

import io
import os
import numpy as np
import librosa
import torch
from transformers import pipeline
from typing import Optional

SR       = 16_000
DEVICE   = os.getenv("DEVICE", "cpu")
DTYPE    = torch.float16 if DEVICE == "cuda" else torch.float32
HF_TOKEN = os.getenv("HF_TOKEN")

_WHISPER_TO_LANG = {
    "rw": "kinyarwanda",
    "en": "english",
}
_LANG_TO_WHISPER = {v: k for k, v in _WHISPER_TO_LANG.items()}
_DEFAULT_LANGUAGE = "kinyarwanda"

_kin_pipe       = None
_eng_pipe       = None
_models_ready   = False
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
        _models_ready   = True
        print("Whisper models loaded.")
    except Exception as e:
        _loading_status = f"error: {e}"
        print(f"Error loading Whisper models: {e}")


def get_models_status() -> dict:
    return {"ready": _models_ready, "status": _loading_status}


def _detect_language(audio: np.ndarray, language_hint: Optional[str] = None) -> str:
    """
    Detect language from audio using Whisper's own internal detection.
    Always runs — language_hint is only used as a tiebreaker when Whisper
    returns an unrecognised language code (not rw or en).

    Args:
        audio         : Full audio array at 16kHz.
        language_hint : Language selected by patient on kiosk screen, or None.

    Returns:
        'kinyarwanda' or 'english'
    """
    clip = audio[: 10 * SR]  # 10 seconds is enough for detection
    try:
        result   = _eng_pipe(
            {"array": clip, "sampling_rate": SR},
            generate_kwargs={"task": "transcribe", "language": None},
            return_timestamps=False,
        )
        detected = result.get("language")
        if detected in _WHISPER_TO_LANG:
            return _WHISPER_TO_LANG[detected]

        # Whisper detected something else (e.g. French, Swahili)
        # Use the hint if available, otherwise fall back to default
        if language_hint in ("kinyarwanda", "english"):
            return language_hint
        return _DEFAULT_LANGUAGE

    except Exception:
        return language_hint if language_hint in ("kinyarwanda", "english") else _DEFAULT_LANGUAGE


def _confidence(chunks: list) -> float:
    if not chunks:
        return 0.0
    bad  = ["[BLANK_AUDIO]", "[MUSIC]"]
    hits = sum(1 for c in chunks if any(t in c.get("text", "") for t in bad))
    return round(max(0.0, 1.0 - hits / len(chunks)), 3)


def transcribe(audio_bytes: bytes, language_hint: Optional[str] = None) -> dict:
    """
    Transcribe raw audio bytes.

    Always detects language from audio — language_hint is never used to skip
    detection. It is only used as a fallback when Whisper's detection returns
    an unrecognised language code.

    Args:
        audio_bytes   : Raw audio file content (wav / mp3 / flac).
        language_hint : Language selected by patient on kiosk screen, or None.

    Returns:
        {
            "full_text":         str,
            "dominant_language": str,
            "mean_confidence":   float,
            "language_source":   str,  # "detected" | "hint_fallback" | "default_fallback"
        }
    """
    if not _models_ready:
        raise RuntimeError(f"Models not ready. Status: {_loading_status}")

    audio, _ = librosa.load(io.BytesIO(audio_bytes), sr=SR, mono=True)

    resolved = _detect_language(audio, language_hint)

    if resolved == language_hint:
        source = "hint_fallback"
    elif language_hint is None and resolved == _DEFAULT_LANGUAGE:
        source = "default_fallback"
    else:
        source = "detected"

    pipe       = _kin_pipe if resolved == "kinyarwanda" else _eng_pipe
    lang_token = _LANG_TO_WHISPER.get(resolved, "rw")

    seg_len  = 30 * SR
    segments = []

    for i in range(0, len(audio), seg_len):
        chunk  = audio[i : i + seg_len]
        result = pipe(
            {"array": chunk, "sampling_rate": SR},
            generate_kwargs={"task": "transcribe", "language": lang_token},
            return_timestamps=True,
        )
        chunks = result.get("chunks", [])
        segments.append({
            "text":       result.get("text", "").strip(),
            "confidence": _confidence(chunks),
        })

    return {
        "full_text":         " ".join(s["text"] for s in segments if s["text"]),
        "dominant_language": resolved,
        "mean_confidence":   round(float(np.mean([s["confidence"] for s in segments])), 3),
        "language_source":   source,
    }
