# Audio Processing Speed Optimization

If transcription takes 2–4+ minutes per clip, the bottleneck is almost always **Whisper on CPU**.

## Quick wins (for demo today)

### 1. Use GPU if available
Add to your `.env`:
```bash
DEVICE=cuda
```
Requires an NVIDIA GPU and `torch` with CUDA. Transcription can drop from 2–4 min to ~10–20 sec per 30s of audio.

### 2. Skip language detection (saves ~30–60s)
Add to your `.env`:
```bash
SKIP_LANG_DETECTION_WHEN_HINTED=true
```
When the user selects Kinyarwanda or English on the screen, the system trusts that choice and skips the extra Whisper pass used for detection. Use this if patients reliably pick their language.

## Fixes already applied

- **Web blob read**: Added missing `xhr.send()` so blob URLs are actually fetched before upload (avoids potential hangs).

## If still slow on CPU

- Whisper large-v3 on CPU is inherently slow (~1–2 min per 30s segment).
- Options: run on a machine with GPU, use a smaller model (requires code changes), or use a cloud STT API for faster processing.
