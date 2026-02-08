"""
Conversational Typhoid Diagnostic API
FastAPI endpoint that handles multi-turn conversations with patients
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict, List
import uuid
from datetime import datetime
import pickle
import numpy as np
import pandas as pd
from sklearn.preprocessing import LabelEncoder, StandardScaler

# ============================================================================
# CONVERSATION SESSION MANAGER
# ============================================================================

class ConversationSession:
    """Manages a single patient consultation session"""
    
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.created_at = datetime.now()
        self.conversation_history = []
        self.collected_data = {}
        self.current_question_index = 0
        self.is_complete = False
        
        # Define all required fields and their questions
        self.questions = {
            'Age': {
                'question': "What is your age?",
                'type': 'number',
                'validation': lambda x: 1 <= int(x) <= 120
            },
            'Gender': {
                'question': "What is your gender? (Male/Female)",
                'type': 'choice',
                'options': ['Male', 'Female']
            },
            'Location': {
                'question': "What type of area do you live in? (Urban/Rural/Endemic)",
                'type': 'choice',
                'options': ['Urban', 'Rural', 'Endemic']
            },
            'Socioeconomic Status': {
                'question': "What is your socioeconomic status? (Low/Middle/High)",
                'type': 'choice',
                'options': ['Low', 'Middle', 'High']
            },
            'Water Source Type': {
                'question': "What is your main source of drinking water? (Tap/Well/River/Untreated Supply)",
                'type': 'choice',
                'options': ['Tap', 'Well', 'River', 'Untreated Supply']
            },
            'Sanitation Facilities': {
                'question': "Do you have proper sanitation facilities? (Proper/Open Defecation)",
                'type': 'choice',
                'options': ['Proper', 'Open Defecation']
            },
            'Hand Hygiene': {
                'question': "Do you practice regular hand hygiene? (Yes/No)",
                'type': 'choice',
                'options': ['Yes', 'No']
            },
            'Consumption of Street Food': {
                'question': "Do you regularly consume street food? (Yes/No)",
                'type': 'choice',
                'options': ['Yes', 'No']
            },
            'Fever Duration (Days)': {
                'question': "For how many days have you had fever? (Enter 0 if no fever)",
                'type': 'number',
                'validation': lambda x: 0 <= int(x) <= 30
            },
            'Gastrointestinal Symptoms': {
                'question': "Do you have any stomach-related symptoms? (None/Diarrhea/Constipation/Abdominal Pain)",
                'type': 'choice',
                'options': ['None', 'Diarrhea', 'Constipation', 'Abdominal Pain']
            },
            'Neurological Symptoms': {
                'question': "Do you have any neurological symptoms? (None/Headache/Confusion/Delirium)",
                'type': 'choice',
                'options': ['None', 'Headache', 'Confusion', 'Delirium']
            },
            'Skin Manifestations': {
                'question': "Do you have any skin rashes or spots? (Yes/No)",
                'type': 'choice',
                'options': ['Yes', 'No']
            },
            'Complications': {
                'question': "Have you experienced any severe complications? (None/Meningitis/Sepsis/Intestinal Perforation)",
                'type': 'choice',
                'options': ['None', 'Meningitis', 'Sepsis', 'Intestinal Perforation']
            },
            'Typhoid Vaccination Status': {
                'question': "Have you received typhoid vaccination? (Received/Not Received)",
                'type': 'choice',
                'options': ['Received', 'Not Received']
            },
            'Previous History of Typhoid': {
                'question': "Have you had typhoid fever before? (Yes/No)",
                'type': 'choice',
                'options': ['Yes', 'No']
            },
            'Weather Condition': {
                'question': "What is the current weather condition? (Hot & Dry/Cold & Humid/Rainy & Wet/Moderate)",
                'type': 'choice',
                'options': ['Hot & Dry', 'Cold & Humid', 'Rainy & Wet', 'Moderate']
            },
            'Ongoing Infection in Society': {
                'question': "Are there any disease outbreaks in your area? (None/Dengue Outbreak/COVID-19 Surge/Seasonal Flu)",
                'type': 'choice',
                'options': ['None', 'Dengue Outbreak', 'COVID-19 Surge', 'Seasonal Flu']
            }
        }
        
        self.field_names = list(self.questions.keys())
    
    def get_next_question(self) -> Optional[Dict]:
        """Get the next question to ask the user"""
        if self.current_question_index >= len(self.field_names):
            return None
        
        field_name = self.field_names[self.current_question_index]
        question_data = self.questions[field_name]
        
        return {
            'field': field_name,
            'question': question_data['question'],
            'type': question_data['type'],
            'options': question_data.get('options', []),
            'progress': f"{self.current_question_index + 1}/{len(self.field_names)}"
        }
    
    def validate_and_store_answer(self, field_name: str, answer: str) -> bool:
        """Validate and store user's answer"""
        if field_name not in self.questions:
            return False
        
        question_data = self.questions[field_name]
        
        # Validate based on type
        if question_data['type'] == 'number':
            try:
                if question_data.get('validation'):
                    if not question_data['validation'](answer):
                        return False
                self.collected_data[field_name] = int(answer)
            except ValueError:
                return False
        
        elif question_data['type'] == 'choice':
            # Case-insensitive matching
            matched = False
            for option in question_data['options']:
                if answer.lower() == option.lower():
                    self.collected_data[field_name] = option
                    matched = True
                    break
            if not matched:
                return False
        
        return True
    
    def add_message(self, role: str, content: str):
        """Add message to conversation history"""
        self.conversation_history.append({
            'role': role,
            'content': content,
            'timestamp': datetime.now().isoformat()
        })


# ============================================================================
# SESSION STORAGE (In-Memory for Demo)
# ============================================================================

# Store active sessions in memory
# In production, use Redis or database
active_sessions: Dict[str, ConversationSession] = {}


# ============================================================================
# TYPHOID MODEL WRAPPER
# ============================================================================

class TyphoidModelWrapper:
    """Wrapper for the typhoid prediction model"""
    
    def __init__(self, model_path: str):
        self.model_path = model_path
        self.load_model()
    
    def load_model(self):
        """Load the trained model"""
        with open(self.model_path, 'rb') as f:
            model_data = pickle.load(f)
        
        self.model = model_data['model']
        self.label_encoders = model_data['label_encoders']
        self.target_encoder = model_data['target_encoder']
        self.scaler = model_data['scaler']
        self.feature_columns = model_data['feature_columns']
    
    def predict(self, patient_data: Dict) -> Dict:
        """Make prediction with probabilities"""
        # Create dataframe
        df = pd.DataFrame([patient_data])
        
        # Handle missing values
        df['Gastrointestinal Symptoms'] = df['Gastrointestinal Symptoms'].fillna('None')
        df['Neurological Symptoms'] = df['Neurological Symptoms'].fillna('None')
        df['Complications'] = df['Complications'].fillna('None')
        df['Ongoing Infection in Society'] = df['Ongoing Infection in Society'].fillna('None')
        
        # Encode categorical features
        for col, encoder in self.label_encoders.items():
            if col in df.columns:
                df[col] = df[col].apply(
                    lambda x: x if x in encoder.classes_ else encoder.classes_[0]
                )
                df[col] = encoder.transform(df[col])
        
        # Scale numerical features
        df[['Age', 'Fever Duration (Days)']] = self.scaler.transform(
            df[['Age', 'Fever Duration (Days)']]
        )
        
        # Select features
        X = df[self.feature_columns]
        
        # Predict
        prediction = self.model.predict(X)[0]
        probabilities = self.model.predict_proba(X)[0]
        
        # Get prediction label
        prediction_label = self.target_encoder.inverse_transform([prediction])[0]
        
        # Create probability dictionary
        prob_dict = {
            class_name: float(probabilities[idx] * 100)
            for idx, class_name in enumerate(self.target_encoder.classes_)
        }
        
        # Calculate severity risk
        severity_risk = self._calculate_severity_risk(prob_dict, patient_data)
        
        # Generate recommendations
        recommendations = self._get_recommendations(prediction_label, severity_risk)
        
        return {
            'prediction': prediction_label,
            'probabilities': prob_dict,
            'severity_risk_percentage': float(severity_risk),
            'confidence': float(max(probabilities) * 100),
            'recommendations': recommendations
        }
    
    def _calculate_severity_risk(self, prob_dict: Dict, patient_data: Dict) -> float:
        """Calculate severity risk percentage"""
        typhoid_risk = (
            prob_dict.get('Acute Typhoid Fever', 0) * 0.5 +
            prob_dict.get('Relapsing Typhoid', 0) * 0.7 +
            prob_dict.get('Complicated Typhoid', 0) * 1.0
        )
        
        if patient_data.get('Fever Duration (Days)', 0) > 7:
            typhoid_risk *= 1.2
        
        if patient_data.get('Complications') not in [None, 'None']:
            typhoid_risk *= 1.3
        
        if patient_data.get('Previous History of Typhoid') == 'Yes':
            typhoid_risk *= 1.1
        
        return min(typhoid_risk, 100)
    
    def _get_recommendations(self, prediction: str, severity: float) -> List[str]:
        """Get clinical recommendations"""
        if prediction == 'Normal or No Typhoid':
            return [
                "Monitor symptoms for the next 24-48 hours",
                "Stay well hydrated",
                "Maintain good hygiene practices",
                "Consult a doctor if symptoms worsen"
            ]
        elif prediction == 'Acute Typhoid Fever':
            recs = [
                "Visit a healthcare facility for confirmation tests",
                "Get blood culture and Widal test done",
                "Do not self-medicate with antibiotics",
                "Maintain strict hygiene and isolation",
                "Stay hydrated and rest"
            ]
            if severity > 60:
                recs.insert(0, "URGENT: Seek medical attention TODAY")
            return recs
        elif prediction == 'Relapsing Typhoid':
            return [
                "Seek immediate medical care",
                "Inform your doctor about previous typhoid history",
                "Complete the full antibiotic course as prescribed",
                "Get follow-up blood cultures done",
                "Strict bed rest required"
            ]
        else:  # Complicated Typhoid
            return [
                "GO TO EMERGENCY ROOM IMMEDIATELY",
                "Hospitalization is likely required",
                "Life-threatening complications are possible",
                "Do not delay treatment"
            ]


# ============================================================================
# FASTAPI APPLICATION
# ============================================================================

app = FastAPI(
    title="Typhoid Diagnostic Conversational API",
    description="AI-powered conversational agent for typhoid fever screening",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize model with correct path
# Assumes structure: project/backend/conversational_api.py and project/model/typhoid_model.pkl
import os
model_path = os.path.join(os.path.dirname(__file__), '..', 'model', 'typhoid_model.pkl')
model = TyphoidModelWrapper(model_path)


# ============================================================================
# PYDANTIC MODELS (Request/Response Schemas)
# ============================================================================

class StartSessionResponse(BaseModel):
    session_id: str
    message: str
    next_question: Dict

class MessageRequest(BaseModel):
    session_id: str
    message: str

class MessageResponse(BaseModel):
    session_id: str
    agent_message: str
    next_question: Optional[Dict] = None
    is_complete: bool = False
    diagnosis: Optional[Dict] = None
    conversation_history: List[Dict]


# ============================================================================
# API ENDPOINTS
# ============================================================================

@app.get("/")
def root():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "Typhoid Diagnostic Conversational API",
        "version": "1.0.0"
    }

@app.post("/conversation/start", response_model=StartSessionResponse)
def start_conversation():
    """
    Start a new consultation session
    Returns session_id and first question
    """
    # Generate unique session ID
    session_id = str(uuid.uuid4())
    
    # Create new session
    session = ConversationSession(session_id)
    active_sessions[session_id] = session
    
    # Get first question
    next_question = session.get_next_question()
    
    # Add to conversation history
    greeting = "Hello! I'm your AI diagnostic assistant for typhoid fever screening. I'll ask you some questions to assess your condition."
    session.add_message('agent', greeting)
    session.add_message('agent', next_question['question'])
    
    return {
        "session_id": session_id,
        "message": greeting,
        "next_question": next_question
    }

@app.post("/conversation/message", response_model=MessageResponse)
def send_message(request: MessageRequest):
    """
    Send a message in an ongoing conversation
    Returns agent's response and next question or final diagnosis
    """
    session_id = request.session_id
    user_message = request.message.strip()
    
    # Check if session exists
    if session_id not in active_sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    session = active_sessions[session_id]
    
    # Add user message to history
    session.add_message('user', user_message)
    
    # Get current field we're asking about
    if session.current_question_index >= len(session.field_names):
        raise HTTPException(status_code=400, detail="Conversation already complete")
    
    current_field = session.field_names[session.current_question_index]
    
    # Validate and store answer
    is_valid = session.validate_and_store_answer(current_field, user_message)
    
    if not is_valid:
        # Invalid answer - ask again with hint
        question_data = session.questions[current_field]
        hint_message = f"I didn't quite understand that. {question_data['question']}"
        
        if question_data['type'] == 'choice':
            hint_message += f"\nPlease choose from: {', '.join(question_data['options'])}"
        
        session.add_message('agent', hint_message)
        
        return {
            "session_id": session_id,
            "agent_message": hint_message,
            "next_question": session.get_next_question(),
            "is_complete": False,
            "conversation_history": session.conversation_history
        }
    
    # Valid answer - move to next question
    session.current_question_index += 1
    
    # Check if we have all data
    if session.current_question_index >= len(session.field_names):
        # All data collected - make prediction
        session.is_complete = True
        
        prediction_result = model.predict(session.collected_data)
        
        # Create final message
        final_message = f"""
Thank you for providing all the information. Based on your symptoms and health profile, here is my assessment:

**Diagnosis:** {prediction_result['prediction']}
**Confidence:** {prediction_result['confidence']:.1f}%
**Severity Risk:** {prediction_result['severity_risk_percentage']:.1f}%

**Probability Breakdown:**
{chr(10).join([f"• {condition}: {prob:.1f}%" for condition, prob in sorted(prediction_result['probabilities'].items(), key=lambda x: x[1], reverse=True)])}

**Recommendations:**
{chr(10).join([f"{i}. {rec}" for i, rec in enumerate(prediction_result['recommendations'], 1)])}

⚠️ **Important:** This is a screening tool and NOT a substitute for professional medical diagnosis. Please consult a healthcare provider for proper diagnosis and treatment.
        """.strip()
        
        session.add_message('agent', final_message)
        
        return {
            "session_id": session_id,
            "agent_message": final_message,
            "next_question": None,
            "is_complete": True,
            "diagnosis": prediction_result,
            "conversation_history": session.conversation_history
        }
    
    # Get next question
    next_question = session.get_next_question()
    acknowledgment = "Got it."
    agent_message = f"{acknowledgment} {next_question['question']}"
    
    session.add_message('agent', agent_message)
    
    return {
        "session_id": session_id,
        "agent_message": agent_message,
        "next_question": next_question,
        "is_complete": False,
        "conversation_history": session.conversation_history
    }

@app.get("/conversation/{session_id}")
def get_conversation(session_id: str):
    """Get full conversation history for a session"""
    if session_id not in active_sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    session = active_sessions[session_id]
    
    return {
        "session_id": session_id,
        "created_at": session.created_at.isoformat(),
        "is_complete": session.is_complete,
        "collected_data": session.collected_data,
        "conversation_history": session.conversation_history
    }

@app.delete("/conversation/{session_id}")
def end_conversation(session_id: str):
    """End and delete a conversation session"""
    if session_id not in active_sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    del active_sessions[session_id]
    
    return {"message": "Session ended successfully"}


# ============================================================================
# RUN SERVER
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    print("Starting server...")
    print(f"Swagger UI: http://localhost:8000/docs")
    print(f"ReDoc: http://localhost:8000/redoc")
    print(f"API Base: http://localhost:8000")
    print("\n")
    uvicorn.run(app, host="0.0.0.0", port=8000)