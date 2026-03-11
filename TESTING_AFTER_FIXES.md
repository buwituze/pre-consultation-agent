## 🔧 Quick Testing Guide After Fixes

### Step 1: Create `.env` file

Copy `.env.example` to `.env` in the `backend/` folder and set these critical values:

```bash
# Minimum required for testing (copy from .env.example):
DB_HOST=localhost
DB_PORT=5432
DB_NAME=pre_consultation_db
DB_USER=postgres
DB_PASSWORD=your_postgres_password

HF_TOKEN=hf_your_huggingface_token_here
DEVICE=cuda  # or 'cpu' if no GPU

USE_DB=true  # or 'false' if testing without database
```

⚠️ **If you don't have a database running**, set `USE_DB=false` to test transcription endpoints only.

---

### Step 2: Start Server

In the Kaggle notebook:

```python
# In a cell:
!cd backend && uvicorn main:app --reload --port 8000 --host 0.0.0.0
```

---

### Step 3: Check Startup Status (New!)

```bash
# Check if everything is initialized
curl https://your-ngrok-url/startup/status

# Expected response while loading:
{
  "database_ready": true,
  "models_ready": false,
  "startup_errors": [],
  "message": "⏳ Still initializing..."
}

# Wait ~30-90 seconds, then check again
# Expected response when ready:
{
  "database_ready": true,
  "models_ready": true,
  "startup_errors": [],
  "message": "✅ All systems ready"
}
```

---

### Step 4: Test Each Endpoint

#### ✅ **Test Kiosk Start** (Database Required)

```bash
curl -X 'POST' \
  'https://your-ngrok-url/kiosk/start' \
  -H 'Content-Type: application/json' \
  -d '{
    "language": "Kinyarwanda",
    "patient_age": 20,
    "patient_name": "Benitha Uwituze",
    "patient_phone": "0790100718",
    "patient_location": "kigali",
    "facility_id": 1
  }'
```

**Expected:**

- ✅ Returns `{"session_id": "...", "greeting": "..."}` (200)
- ❌ Was: 503 error
- ❌ Now returns error with message if database not ready

---

#### ✅ **Test Transcription** (No Database Needed)

```bash
curl -X 'POST' \
  'https://your-ngrok-url/sessions/103af743-bec3-4a59-88ca-5e368be496a4/audio' \
  -H 'accept: application/json' \
  -F 'audio=@your_audio_file.wav;type=audio/wav' \
  -F 'language=kinyarwanda'
```

**Expected:**

- ✅ Returns transcription with confidence scores (200)
- ❌ Was: "Failed to fetch" if models not ready
- ✅ Now returns 503 with message: `"AI models still loading (loading_kinyarwanda_model)"`

---

#### ✅ **Check Model Status** (New!)

```bash
curl https://your-ngrok-url/models/status
```

**Expected responses:**

- While loading: `{"ready": false, "status": "loading_kinyarwanda_model"}`
- After 5 min timeout: `{"ready": false, "status": "error: timeout after 5 minutes"}`
- When ready: `{"ready": true, "status": "ready"}`

---

### Troubleshooting

| Symptom                                                    | Cause                                         | Solution                                                |
| ---------------------------------------------------------- | --------------------------------------------- | ------------------------------------------------------- |
| `/startup/status` shows `database_ready: false`            | No `.env` file or DB connection details wrong | Create `.env` with correct DB credentials               |
| `/startup/status` shows `models_ready: false` after 5+ min | Model loading failed                          | Check logs for error, check HF_TOKEN                    |
| `/kiosk/start` returns 503                                 | Database not initialized                      | Ensure PostgreSQL is running, check `/startup/status`   |
| `/sessions/{id}/audio` returns 503                         | Models still loading                          | Wait for `/startup/status` to show `models_ready: true` |
| `/models/status` shows "error: timeout..."                 | Whisper models took >5 min to load            | Increase timeout in `main.py` line ~50                  |

---

### What Changed

- 🆕 `/startup/status` endpoint shows exactly what's wrong
- 🆕 5-minute timeout for model loading (prevents infinite "loading" state)
- 🆕 Better 503 error messages (instead of silent crashes)
- 🆕 `/health` now includes diagnostic flags
- ✅ Database errors raise 503 instead of crashing the server
- ✅ Transcription validates models are ready first

**Result:** You'll now see helpful error messages instead of confusing ngrok errors.
