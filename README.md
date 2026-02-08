# Pre-Consultation Agent

A voice-based AI model for triaging and assessing typhoid fever in rural populations.

## Overview

This conversational AI model helps triage typhoid fever by checking for key symptoms including fever, abdominal pain, and gastrointestinal signs. The model interacts with users through natural conversation, asking clarifying questions before making assessments.

Based on the symptoms identified, the model provides:

- Initial guidance and support for patients
- Recommendations for escalation to healthcare professionals when symptoms indicate severe conditions or no improvement

This approach reduces the burden on doctors, improves access to timely care, and ensures patients receive appropriate attention.

## Project Structure

```
pre-consultation-agent/
├── backend/
│   ├── conversationalAPI.py    # FastAPI conversational endpoint
│   └── requirements.txt         # Python dependencies
├── frontend/                     # User interface
├── model/                        # Typhoid prediction model
│   └── typhoid_model_pred.ipynb
├── testing/
│   └── testconversation.py      # CLI test client
└── README.md
```

## Setup

1. **Install Dependencies**

   ```bash
   cd backend
   pip install -r requirements.txt
   ```

2. **Start the Backend API**

   ```bash
   cd backend
   uvicorn conversationalAPI:app --reload
   ```

   The API will be available at `http://localhost:8000`

## Testing

### Option 1: Swagger UI (Interactive API Documentation)

1. Start the backend API
2. Open your browser and navigate to `http://localhost:8000/docs`
3. Test the API endpoints directly through the Swagger UI interface

### Option 2: CLI Test Client

1. Ensure the backend API is running
2. Run the test conversation script:
   ```bash
   cd testing
   python testconversation.py
   ```
3. Follow the prompts to simulate a patient consultation
