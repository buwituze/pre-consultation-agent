# Pre-Consultation Agent

A hospital-owned, voice-based pre-consultation and triage agent that acts as a data collection point in a hospital.

## Solution

This system is installed as hospital equipment, not a personal app, to:

- Prevent misuse
- Ensure supervised use
- Allow access for patients without smartphones or digital literacy
- Support Kinyarwanda and English voice interaction

**Acts as a supervised consultation support tool, not a diagnostic system.**

## Scenario

A patient arrives at a hospital and avoids waiting nearly 4 hours for a 5-minute consultation. Instead, the patient speaks to the voice-based system in Kinyarwanda or English.

The system asks questions to clarify the patient's issue and forwards the summary to a doctor with a suggestion on what could be the issue. The system can also put a patient on a queue to get an examination and/or direct them to where they need to get to next (such as a particular doctor or department).

The doctor reviews the information and decides on what the patient needs as usual, like whether they should prioritize the patient for examination and next steps.

## Key Features

- **Voice-based interaction** in Kinyarwanda and English
- **Pre-consultation triage** to reduce waiting times
- **Data collection** for healthcare workers
- **Patient routing** to appropriate departments
- **Doctor summaries** with suggested next steps
- **Queue management** for examinations

## Project Structure

```
pre-consultation-agent/
├── backend/
│   ├── main.py                   # FastAPI main application
│   ├── routing.py                # Request routing logic
│   ├── session.py                # Session management
│   ├── requirements.txt          # Python dependencies
│   ├── database/                 # Database layer
│   │   ├── database.py           # Database connection and queries
│   │   └── schema.sql            # Database schema
│   ├── models/                   # ML model implementations
│   │   ├── model_a.py            # Speech-to-text
│   │   ├── model_b.py            # Language understanding
│   │   ├── model_c.py            # Dialogue policy
│   │   ├── model_d.py            # Risk scoring
│   │   ├── model_e.py            # Patient guidance
│   │   └── model_f.py            # Doctor summary
│   └── routers/                  # API endpoints
│       ├── dialogue.py           # Conversation endpoints
│       ├── doctor.py             # Doctor interface
│       ├── kiosk.py              # Kiosk interface
│       ├── sessions.py           # Session management
│       ├── transcription.py      # Audio transcription
│       └── triage.py             # Triage logic
├── frontend/                     # Flutter mobile/kiosk interface
│   ├── lib/
│   │   ├── main.dart             # App entry point
│   │   ├── screens/              # UI screens
│   │   └── services/             # API services
│   └── assets/
│       └── translations/         # Kinyarwanda & English
├── notebooks/                    # Model development notebooks
├── testing/                      # Testing scripts
└── README.md                     # Project overview
```

## Setup

Setup a virtual environment:

- Create a venv `python -m venv venv`
- Activate the venv `source venv/Scripts/activate`
- Deactivate the venv `deactivate`

1. **Install Dependencies**

   ```bash
   cd backend
   pip install -r requirements.txt
   ```

2. **Start the Backend API**

   ```bash
   cd backend
   python main.py
   ```

   The API will be available at `http://localhost:8000`

## Testing

### Option 1: via the Swagger UI (Interactive API Documentation)

1. Start the backend API
2. Open your browser and navigate to `http://localhost:8000/docs`
3. Test the API endpoints directly through the Swagger UI interface

### Option 2: via the Terminal

1. Ensure the backend API is running
2. Run the test conversation script:
   ```bash
   cd testing
   python testconversation.py
   ```
3. Follow the prompts and answer questions to simulate a patient consultation

## System Architecture

The system uses a multi-model pipeline to process patient interactions:

1. **Model A (Speech-to-Text)**: Converts Kinyarwanda/English voice input to text
2. **Model B (Language Understanding)**: Extracts symptoms and intent from patient responses
3. **Model C (Dialogue Policy)**: Determines the next question to ask
4. **Model D (Risk Scoring)**: Assesses urgency and severity of symptoms
5. **Model E (Patient Guidance)**: Provides immediate support and directions
6. **Model F (Doctor Summary)**: Generates comprehensive summaries for healthcare workers

Each model works together to create a seamless, supervised consultation experience that collects structured data for medical review.
