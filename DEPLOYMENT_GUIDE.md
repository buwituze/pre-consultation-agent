# 🚀 New System Deployment Guide

## Overview

This guide documents the complete implementation of the two-stage extraction system with intelligent routing designed to reduce API costs by 40-50% while maintaining accuracy.

**System Version:** 2.0 (Two-Stage Extraction + Routing)  
**Implementation Date:** January 2025  
**Cost Target:** $0.002/patient (down from $0.004)  
**Initial Coverage:** 4 symptoms + patient info

---

## 📋 What Changed

### Architecture

**OLD SYSTEM:**

- Single-pass full extraction (13 API calls/patient)
- AI questions for all symptoms
- No cost optimization
- ~$0.004 per patient

**NEW SYSTEM:**

- Two-stage extraction (light → route → full)
- Intelligent routing: emergency → rule-based → AI
- Hybrid question approach (rules + AI)
- 6-10 API calls/patient
- ~$0.002 per patient (50% savings)

---

## 📁 Files Modified/Created

### ✅ Modified Files

1. **`backend/models/model_a.py`**
   - Added quality assessment: `_assess_quality(confidence)`
   - Returns `quality` field: "high", "medium", "low"
   - Used for routing decisions

2. **`backend/models/model_b.py`** (COMPLETE REWRITE)
   - **New:** `extract_light()` — Quick routing extraction (~300 tokens)
   - **New:** `extract_full()` — Comprehensive extraction (~800 tokens)
   - **New:** `_cleanup_mixed_language()` — Normalize Kinyarwanda/English/French
   - **New:** `_detect_red_flags()` — Safety keyword detection

### ✅ New Files Created

3. **`backend/models/model_c_rules.py`** — Rule-based question trees
   - Patient info questions (name, age, gender) in both languages
   - 4 symptom trees: mouth_problems, stomach_pain, headache, backache
   - 3 questions per symptom with red flag checks
   - Fallback to AI for unknown symptoms

4. **`backend/routing/conversation_router.py`** — Central routing logic
   - `route_conversation()` — Main decision engine
   - 3 modes: emergency, rule_based, ai_powered
   - Cost estimation and analytics

5. **`backend/routing/__init__.py`** — Package exports

6. **`backend/database/migrations/add_new_system_fields.sql`** — Schema updates
   - Adds 10 new fields to session table
   - Tracks: conversation mode, API calls, costs, routing reasoning

7. **`backend/utils/session_logger.py`** — Session tracking & analytics
   - Log all sessions with mode/cost/API call tracking
   - Unknown symptom logging for expansion
   - Performance reports and cost analysis

8. **`DEPLOYMENT_GUIDE.md`** — This file

---

## 🔧 Deployment Steps

### Step 1: Backup Current System

```powershell
# Backup database
pg_dump -U your_username pre_consultation_db > backup_$(Get-Date -Format 'yyyyMMdd_HHmmss').sql

# Backup old Model B (already done as model_b_old_backup.py)
```

### Step 2: Update Dependencies

Make sure `google-genai` package is version 0.2.0 or higher:

```powershell
pip install --upgrade google-genai
```

### Step 3: Run Database Migration

```powershell
# Connect to PostgreSQL
psql -U your_username -d pre_consultation_db

# Run migration
\i backend/database/migrations/add_new_system_fields.sql

# Verify new fields
\d session

# Expected output should include:
# - conversation_mode
# - api_calls_count
# - cost_estimate
# - transcription_quality
# - patient_age
# - patient_gender
# - chief_complaint
# - routing_reasoning
# - severity_estimate
# - red_flags_detected

\q
```

### Step 4: Create Utils Directory (if needed)

```powershell
# Create utils directory if it doesn't exist
New-Item -ItemType Directory -Force -Path backend/utils
```

### Step 5: Update API Environment Variables

Ensure your `.env` file has:

```env
GOOGLE_API_KEY=your_key_here
GEMINI_MODEL=gemini-1.5-flash-latest
```

### Step 6: Test Individual Components

```powershell
cd backend

# Test Model A (quality assessment)
python -c "from models.model_a import transcribe; print(transcribe('path/to/test/audio.wav'))"

# Test Model B light extraction
python -c "from models.model_b import extract_light; print(extract_light('Patient says: I have a headache that started 3 days ago'))"

# Test Model C rules
python -c "from models.model_c_rules import get_symptom_questions; print(get_symptom_questions('headache', 'en'))"

# Test conversation router
python routing/conversation_router.py

# Test session logger
python utils/session_logger.py
```

### Step 7: Integration Testing

Create a test script to verify end-to-end flow:

```python
# backend/test_new_system.py
from models.model_a import transcribe
from models.model_b import extract_light
from routing.conversation_router import route_conversation
from models.model_c_rules import get_symptom_questions
from utils.session_logger import log_session
import datetime

# Test audio file
audio_path = "data/audio/test_headache.wav"

# Step 1: Transcribe
transcription = transcribe(audio_path)
print(f"Transcription: {transcription}")

# Step 2: Light extraction
light_result = extract_light(transcription['full_text'])
print(f"Light extraction: {light_result}")

# Step 3: Route conversation
routing = route_conversation(
    light_extraction=light_result,
    transcription_quality=transcription['quality'],
    language=transcription['dominant_language']
)
print(f"Routing: {routing}")

# Step 4: Get questions (if rule-based)
if routing['mode'] == 'rule_based':
    questions = routing['questions']
    print(f"Questions: {questions}")

# Step 5: Log session
session_data = {
    "session_id": "test_001",
    "patient_id": 1,
    "conversation_mode": routing['mode'],
    "chief_complaint": light_result['chief_complaint'],
    "severity_estimate": light_result['severity_estimate'],
    "red_flags_detected": light_result['red_flags_present'],
    "transcription_quality": transcription['quality'],
    "api_calls_count": 7,
    "cost_estimate": 0.0028,
    "routing_reasoning": routing['reasoning'],
    "timestamp": datetime.datetime.now().isoformat(),
    "patient_age": None,
    "patient_gender": None
}
log_session(session_data)

print("\n✅ End-to-end test complete!")
```

Run the test:

```powershell
python backend/test_new_system.py
```

### Step 8: Update API Endpoints (Next Phase)

After successful component testing, update these files:

- `backend/routers/transcription.py`
- `backend/routers/dialogue.py`
- `backend/routers/sessions.py`

(Detailed endpoint updates will be documented separately)

---

## 📊 Monitoring & Analytics

### Real-Time Monitoring

```python
from utils.session_logger import generate_performance_report, generate_expansion_report

# Daily performance check
print(generate_performance_report(days=1))

# Weekly cost analysis
print(generate_performance_report(days=7))

# Check expansion opportunities
print(generate_expansion_report())
```

### Key Metrics to Track

1. **Route Distribution**
   - Target: 60% rule-based, 30% AI-powered, 10% emergency
   - Monitor: If AI-powered > 40%, consider adding more symptoms

2. **Cost Per Session**
   - Target: $0.002/session
   - Alert if: > $0.003/session

3. **API Calls Per Session**
   - Target: 7-8 calls average
   - Alert if: > 10 calls average

4. **Unknown Symptoms**
   - Review weekly for expansion candidates
   - Add new symptom when ≥3 occurrences in a week

5. **Red Flag Detection Rate**
   - Expected: 5-10% of sessions
   - Alert if: Sudden spike (>20%)

### Database Queries for Analytics

```sql
-- Daily mode distribution
SELECT
    conversation_mode,
    COUNT(*) as sessions,
    ROUND(AVG(api_calls_count), 2) as avg_api_calls,
    ROUND(AVG(cost_estimate), 4) as avg_cost
FROM session
WHERE start_time >= NOW() - INTERVAL '1 day'
GROUP BY conversation_mode;

-- Top unknown symptoms (for expansion)
SELECT
    chief_complaint,
    COUNT(*) as occurrences
FROM session
WHERE conversation_mode = 'ai_powered'
    AND routing_reasoning LIKE '%unknown%'
    AND start_time >= NOW() - INTERVAL '7 days'
GROUP BY chief_complaint
HAVING COUNT(*) >= 3
ORDER BY occurrences DESC;

-- Cost savings calculation
SELECT
    COUNT(*) as total_sessions,
    ROUND(SUM(cost_estimate), 2) as actual_cost,
    ROUND(COUNT(*) * 0.0052, 2) as all_ai_cost,
    ROUND(COUNT(*) * 0.0052 - SUM(cost_estimate), 2) as savings,
    ROUND(((COUNT(*) * 0.0052 - SUM(cost_estimate)) / (COUNT(*) * 0.0052)) * 100, 1) as savings_percentage
FROM session
WHERE start_time >= NOW() - INTERVAL '30 days';

-- Red flag detection
SELECT
    DATE(start_time) as date,
    COUNT(*) as total_sessions,
    SUM(CASE WHEN red_flags_detected THEN 1 ELSE 0 END) as red_flag_sessions,
    ROUND(SUM(CASE WHEN red_flags_detected THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1) as red_flag_percentage
FROM session
WHERE start_time >= NOW() - INTERVAL '7 days'
GROUP BY DATE(start_time)
ORDER BY date DESC;
```

---

## 🧪 Testing Scenarios

### Test Case 1: Known Symptom (Rule-Based Path)

**Input:** "I have a headache that started 2 days ago"  
**Expected Route:** rule_based  
**Expected Questions:** 3 targeted headache questions  
**Expected API Calls:** 7  
**Expected Cost:** ~$0.0028

### Test Case 2: High Severity (AI Path)

**Input:** "I have severe stomach pain, vomiting, can't stand"  
**Expected Route:** ai_powered  
**Expected Reason:** High severity (8-9/10)  
**Expected API Calls:** 10  
**Expected Cost:** ~$0.0040

### Test Case 3: Red Flag (Emergency Path)

**Input:** "Chest pain, difficulty breathing, left arm numb"  
**Expected Route:** emergency  
**Expected Action:** Immediate escalation  
**Expected API Calls:** 6  
**Expected Cost:** ~$0.0024

### Test Case 4: Unknown Symptom (AI Path + Logging)

**Input:** "I have a weird rash on my back"  
**Expected Route:** ai_powered  
**Expected Reason:** Unknown symptom  
**Expected API Calls:** 10  
**Expected Cost:** ~$0.0040  
**Expected Action:** Log for expansion

---

## 📈 Expansion Planning

### When to Add New Symptoms

Add a symptom to rule-based questions when:

1. **Frequency:** ≥3 occurrences per week
2. **Pattern:** Questions follow predictable pattern
3. **Safety:** Red flags can be defined clearly
4. **Common:** Appears in top 10 unknown symptoms

### How to Add a New Symptom

1. **Design Questions (3-5 questions)**

   ```python
   # In backend/models/model_c_rules.py
   'new_symptom': {
       'questions': [
           ('en', "When did the symptom start?"),
           ('rw', "Ni ryari ibimenyetso byatangiye?"),
           # ... more questions
       ],
       'red_flags': ['keyword1', 'keyword2']
   }
   ```

2. **Add Normalization Mapping**

   ```python
   # In normalize_complaint()
   'variation1': 'new_symptom',
   'variation2': 'new_symptom',
   ```

3. **Test with Real Data**
   - Use logged unknown symptom sessions
   - Verify questions cover common patterns
   - Check red flag detection

4. **Deploy & Monitor**
   - Track routing changes
   - Verify cost reduction
   - Adjust questions as needed

---

## 🚨 Troubleshooting

### Issue: High AI-Powered Percentage (>50%)

**Possible Causes:**

- Unknown symptoms more common than expected
- Severity threshold too low (currently 5)
- Transcription quality poor

**Solutions:**

- Review unknown symptoms for expansion opportunities
- Consider adjusting severity threshold to 6
- Improve audio quality/preprocessing

### Issue: Cost Higher Than Expected

**Possible Causes:**

- More complex conversations than estimated
- API call count higher than projected
- Model responses longer than expected

**Solutions:**

- Review API call logs per session
- Optimize prompts to reduce token usage
- Consider stricter routing to rule-based

### Issue: Red Flags Missed

**Possible Causes:**

- Keyword list incomplete
- Mixed language not cleaned properly
- Symptom-specific flags missing

**Solutions:**

- Review red flag missed cases
- Expand keyword lists
- Add symptom-specific red flag checks

### Issue: Questions Not Relevant

**Possible Causes:**

- Complaint normalization failed
- Variations not captured
- Language detection wrong

**Solutions:**

- Add more normalization mappings
- Improve language cleanup
- Log mismatches for review

---

## 📝 Current System Coverage

### Patient Information (Always Asked First)

- Name
- Age
- Gender

### Covered Symptoms (Rule-Based Questions Available)

1. **Headache** (`headache`, `umutwe`, `head pain`)
2. **Stomach Pain** (`stomach_pain`, `inda iriho`, `abdominal pain`)
3. **Mouth Problems** (`mouth_problems`, `ibibazo byomunwa`, `tooth pain`, `toothache`)
4. **Backache** (`backache`, `umugongo`, `back pain`)

### All Other Symptoms

- Routed to AI-powered conversation
- Logged for expansion planning
- Full LLU extraction applied

---

## 🎯 Success Criteria

After 1 week of production use:

- [ ] Rule-based path handles ≥50% of sessions
- [ ] Average cost per session ≤ $0.0025
- [ ] Red flag detection catches all emergency cases
- [ ] No patient complaints about question relevance
- [ ] ≥3 new expansion candidates identified

After 1 month of production use:

- [ ] Cost savings ≥40% vs old system
- [ ] 6-8 symptoms covered by rules
- [ ] AI-powered path only for complex/rare cases
- [ ] Patient satisfaction maintained or improved

---

## 📚 Additional Resources

- **Old System Backup:** `backend/models/model_b_old_backup.py`
- **API Documentation:** Google Gemini Flash API (v1beta)
- **Database Schema:** `backend/database/schema.sql`
- **Test Audio:** `backend/data/audio/` (if available)

---

## 🔐 Rollback Plan

If critical issues arise:

1. **Database Rollback:**

   ```sql
   -- Remove new fields
   ALTER TABLE session
   DROP COLUMN IF EXISTS conversation_mode,
   DROP COLUMN IF EXISTS api_calls_count,
   -- ... (all new fields)
   ```

2. **Code Rollback:**

   ```powershell
   # Restore old Model B
   Copy-Item backend/models/model_b_old_backup.py backend/models/model_b.py -Force

   # Remove new files
   Remove-Item backend/routing -Recurse
   Remove-Item backend/models/model_c_rules.py
   Remove-Item backend/utils/session_logger.py
   ```

3. **Restart Services:**
   ```powershell
   # Restart backend server
   ```

---

## ✅ Deployment Checklist

- [ ] Backup current database
- [ ] Update `google-genai` package
- [ ] Run database migration
- [ ] Verify new fields in session table
- [ ] Test Model A quality assessment
- [ ] Test Model B light/full extraction
- [ ] Test Model C rule questions
- [ ] Test conversation router
- [ ] Test session logger
- [ ] Run end-to-end integration test
- [ ] Review monitoring dashboard
- [ ] Document any custom modifications
- [ ] Train team on new system
- [ ] Set up alerting for cost spikes
- [ ] Schedule weekly expansion reviews

---

**Questions? Issues?** Document them in the session for review!
