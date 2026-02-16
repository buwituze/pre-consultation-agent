# Backend - Pre-Consultation Agent

Voice-based medical consultation system backend with PostgreSQL database.

## Quick Setup

### 1. Database

```bash
createdb pre_consultation_db
psql -U postgres -d pre_consultation_db -f schema.sql
```

### 2. Configuration

Create `.env`:

```env
DB_HOST=localhost
DB_PORT=5432
DB_NAME=pre_consultation_db
DB_USER=postgres
DB_PASSWORD=your_password
```

### 3. Dependencies

```bash
pip install -r requirements.txt
```

### 4. Test Database

```bash
cd ../testing
python test_database.py
```

### 5. Run API

```bash
python conversationalAPI.py
```

## Python Usage

```python
from database import DatabaseConnection, PatientDB, SessionDB

DatabaseConnection.initialize_pool()

patient = PatientDB.create_patient("Marie Uwimana", "+250788123456", "kinyarwanda")
session = SessionDB.create_session(patient['patient_id'])
SessionDB.update_prediction_info(session['session_id'], "Suspected Typhoid", 0.8523)
SessionDB.close_session(session['session_id'])
```

## Database Tables

- `patient` - Patient records
- `healthcare_worker` - Medical staff
- `session` - Consultation sessions
- `conversation_message` - Message history
- `symptom` - Extracted symptoms
- `prediction` - ML predictions
- `prescription` - Medications prescribed

## Views

- `v_session_overview` - Complete session details
- `v_sessions_awaiting_review` - Sessions needing review
- `v_worker_activity` - Worker statistics

## Functions

- `close_session(session_id)` - Close session
- `get_patient_history(patient_id)` - Get patient history

## Backup

```bash
pg_dump -U postgres pre_consultation_db > backup.sql
psql -U postgres pre_consultation_db < backup.sql
```
