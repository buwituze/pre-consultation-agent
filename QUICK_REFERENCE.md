# 🔍 Quick Reference Guide

## One-Page Overview of the New System

---

## 🎯 Three Routing Modes

| Mode           | When Used                    | Questions       | API Calls | Cost    |
| -------------- | ---------------------------- | --------------- | --------- | ------- |
| **EMERGENCY**  | Red flags detected           | Limited, urgent | 6         | $0.0024 |
| **RULE-BASED** | Known symptom + low severity | 3 predefined    | 7         | $0.0028 |
| **AI-POWERED** | Unknown OR high severity     | AI adaptive     | 10        | $0.0040 |

**Routing Logic:**

```
Red flags? → EMERGENCY
Known symptom + severity < 5 + quality high? → RULE-BASED
Else → AI-POWERED
```

---

## 📦 Core Components

### Model A (Whisper)

```python
from models.model_a import transcribe

result = transcribe(audio_path)
# Returns: full_text, dominant_language, mean_confidence, quality
```

### Model B (Extraction)

```python
from models.model_b import extract_light, extract_full

# Stage 1: Light extraction for routing
light = extract_light(transcript)
# Returns: chief_complaint, severity_estimate, red_flags_present, clarity

# Stage 2: Full extraction after conversation
full = extract_full(transcript, conversation_history, target_language)
# Returns: comprehensive clinical data
```

### Model C Rules (Questions)

```python
from models.model_c_rules import get_symptom_questions, normalize_complaint

# Normalize complaint
complaint = normalize_complaint("umutwe urandwara")  # → "headache"

# Get questions
questions = get_symptom_questions(complaint, language="rw")
# Returns: list of 3 questions or None (use AI)
```

### Conversation Router

```python
from routing.conversation_router import route_conversation

routing = route_conversation(
    light_extraction=light_result,
    transcription_quality="high",
    language="rw"
)
# Returns: mode, questions, max_turns, reasoning, red_flag_checks
```

### Session Logger

```python
from utils.session_logger import log_session, generate_performance_report

# Log completed session
log_session({
    "session_id": "...",
    "conversation_mode": "rule_based",
    "api_calls_count": 7,
    "cost_estimate": 0.0028,
    # ... other fields
})

# Generate reports
print(generate_performance_report(days=7))
```

---

## 🗂️ Covered Symptoms (Rule-Based)

| Complaint          | Variations                   | Red Flags                         |
| ------------------ | ---------------------------- | --------------------------------- |
| **headache**       | umutwe, head pain, migraine  | severe, sudden, vision, confusion |
| **stomach_pain**   | inda iriho, abdominal pain   | vomiting, severe, blood           |
| **mouth_problems** | ibibazo byomunwa, tooth pain | swelling, bleeding, fever         |
| **backache**       | umugongo, back pain          | numbness, weakness, trauma        |

**Unknown symptoms** → AI-powered + logged for expansion

---

## 💾 Database Fields (Session Table)

**New Fields Added:**

- `conversation_mode` (emergency/rule_based/ai_powered)
- `api_calls_count` (integer)
- `cost_estimate` (decimal)
- `transcription_quality` (high/medium/low)
- `patient_age` (integer)
- `patient_gender` (text)
- `chief_complaint` (text)
- `routing_reasoning` (text)
- `severity_estimate` (integer 1-10)
- `red_flags_detected` (boolean)

---

## 📊 Quick Analytics Queries

### Today's Stats

```sql
SELECT conversation_mode, COUNT(*), ROUND(AVG(cost_estimate), 4)
FROM session
WHERE start_time >= CURRENT_DATE
GROUP BY conversation_mode;
```

### Unknown Symptoms

```sql
SELECT chief_complaint, COUNT(*)
FROM session
WHERE conversation_mode = 'ai_powered'
  AND routing_reasoning LIKE '%unknown%'
  AND start_time >= CURRENT_DATE - 7
GROUP BY chief_complaint
HAVING COUNT(*) >= 3
ORDER BY COUNT(*) DESC;
```

### Cost Savings

```sql
SELECT
    COUNT(*) as sessions,
    ROUND(SUM(cost_estimate), 2) as actual,
    ROUND(COUNT(*) * 0.0052, 2) as if_all_ai,
    ROUND((1 - SUM(cost_estimate)/(COUNT(*)*0.0052)) * 100, 1) as savings_pct
FROM session
WHERE start_time >= CURRENT_DATE - 30;
```

---

## 🚨 Red Flag Keywords

**General:** chest pain, difficulty breathing, unconscious, severe bleeding, seizure

**Headache:** sudden severe, worst headache, vision loss, confusion, stiff neck

**Stomach:** severe pain, vomiting blood, black stool, rigid abdomen

**Mouth:** difficulty swallowing, airway obstruction, severe swelling

**Back:** leg numbness, loss of bowel control, trauma, can't walk

---

## 🔄 Typical Session Flow

```
1. Patient speaks [Audio recorded]
   ↓
2. Model A transcribes [quality assessed]
   ↓
3. Model B light extract [complaint, severity, red flags]
   ↓
4. Router decides [emergency/rule/ai]
   ↓
5a. RULE PATH: Get 3 questions → Ask → Collect
5b. AI PATH: AI conversation → Adaptive questions
   ↓
6. Model B full extract [comprehensive data]
   ↓
7. Models C-F [triage, risk, guidance, summary]
   ↓
8. Log session [mode, cost, API calls]
```

---

## 💰 Cost Breakdown

| Component            | Tokens | Cost     |
| -------------------- | ------ | -------- |
| Light extract        | ~300   | $0.00012 |
| Full extract         | ~800   | $0.00032 |
| Single question (AI) | ~150   | $0.00006 |
| Triage (Model D)     | ~400   | $0.00016 |

**Rule-Based Session:** Light + 3 questions + Full + Triage = ~$0.0028  
**AI Session:** Light + 6 questions + Full + Triage = ~$0.0040  
**Emergency:** Light + 2 questions + Full + Triage = ~$0.0024

---

## 🧪 Testing Commands

```powershell
# Test router
python backend/routing/conversation_router.py

# Test logger
python backend/utils/session_logger.py

# Test Model B light
python -c "from backend.models.model_b import extract_light; print(extract_light('I have a headache since 2 days'))"

# Test Model C rules
python -c "from backend.models.model_c_rules import get_symptom_questions; print(get_symptom_questions('headache', 'en'))"

# Run migration
psql -U user -d db_name -f backend/database/migrations/add_new_system_fields.sql
```

---

## 📈 Target Metrics

| Metric             | Target   | Current (Baseline) |
| ------------------ | -------- | ------------------ |
| Rule-based %       | ≥60%     | 0% (all AI)        |
| Avg cost/session   | ≤$0.0025 | $0.0052            |
| API calls/session  | ≤8       | 13                 |
| Red flag detection | 100%     | TBD                |
| Savings            | ≥40%     | 0%                 |

---

## 🛠️ Adding New Symptom (Quick)

1. **Add to Model C Rules:**

```python
'new_symptom': {
    'questions': [
        ('en', "Question 1?"),
        ('rw', "Ikibazo 1?"),
        ('en', "Question 2?"),
        ('rw', "Ikibazo 2?"),
        ('en', "Question 3?"),
        ('rw', "Ikibazo 3?"),
    ],
    'red_flags': ['keyword1', 'keyword2']
}
```

2. **Add normalization:**

```python
'variation1': 'new_symptom',
'variation2': 'new_symptom',
```

3. **Test & Deploy**

---

## 📞 Quick Troubleshooting

| Issue                      | Check                   | Fix                        |
| -------------------------- | ----------------------- | -------------------------- |
| High AI %                  | Unknown symptoms log    | Add more symptoms to rules |
| High cost                  | API calls per mode      | Optimize prompts           |
| Missed red flags           | Review keywords         | Expand red flag lists      |
| Wrong questions            | Complaint normalization | Add more variations        |
| Poor quality transcription | Audio quality, model    | Improve preprocessing      |

---

## 📁 File Locations

```
backend/
├── models/
│   ├── model_a.py          # Whisper + quality
│   ├── model_b.py          # Light + Full extraction
│   └── model_c_rules.py    # Rule questions
├── routing/
│   └── conversation_router.py  # Router logic
├── utils/
│   └── session_logger.py   # Logging & analytics
└── database/
    └── migrations/
        └── add_new_system_fields.sql
```

---

## 🎯 Remember

1. **Always ask patient info first** (name, age, gender)
2. **Red flags = immediate emergency protocol**
3. **Unknown symptoms → AI + log for expansion**
4. **Review expansion report weekly**
5. **Monitor cost daily in early stages**
6. **Add symptoms when ≥3 occurrences**

---

**Quick Start:** Run migration → Test components → Update endpoints → Deploy → Monitor

**Help:** See DEPLOYMENT_GUIDE.md for detailed instructions
