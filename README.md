# Pre-Consultation Agent

A voice-based AI model for triaging and assessing typhoid fever in rural populations.

#### Video Demo: (here)[]

#### Dataset: (Typhoid Fever Dataset)[https://www.kaggle.com/datasets/rajmohnani12/typhoid-dataset]

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
│   ├── conversationalAPI.py      # FastAPI conversational endpoint
│   └── requirements.txt          # Python dependencies
│   └── ReadMe.md
├── frontend/                     # User interface
├── model/                        # Typhoid prediction model
|   └── typhoid_model.pkl         # saved trained model
│   └── ReadMe.md
├── testing/                      # Testing scripts
│   └── testconversation.py       # CLI test client
├── typhoid_pred_model.ipynb      # notebook
└── README.md                     # project overview and usage guideance
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
   uvicorn conversationalAPI:app --reload
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

## Model Architecture

This model uses the Gradient Boosting Classifier algorithm. This algorithm is excellent for tabular modeical data and it handles non-linear relationships relatively well. Gradient Boosting Classifier also provides probability estimates and is robust when handling outliers and missing data.

![alt text](<Assests/model achitecture.png>)
