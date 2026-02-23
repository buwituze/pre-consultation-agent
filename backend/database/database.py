import os
import logging
import json
from typing import Optional, Dict, List, Any, Tuple
from contextlib import contextmanager
import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DatabaseConnection:
    _connection_pool: Optional[pool.ThreadedConnectionPool] = None
    
    @classmethod
    def initialize_pool(cls, min_conn: int = 1, max_conn: int = 10):
        if cls._connection_pool is not None:
            logger.warning("Connection pool already initialized")
            return
        
        try:
            cls._connection_pool = pool.ThreadedConnectionPool(
                min_conn, max_conn,
                host=os.getenv('DB_HOST', 'localhost'),
                port=os.getenv('DB_PORT', '5432'),
                database=os.getenv('DB_NAME', 'pre_consultation_db'),
                user=os.getenv('DB_USER', 'postgres'),
                password=os.getenv('DB_PASSWORD', ''),
                cursor_factory=RealDictCursor
            )
            logger.info("Database connection pool initialized")
        except Exception as e:
            logger.error(f"Failed to initialize connection pool: {e}")
            raise
    
    @classmethod
    def close_pool(cls):
        if cls._connection_pool:
            cls._connection_pool.closeall()
            cls._connection_pool = None
            logger.info("Database connection pool closed")
    
    @classmethod
    @contextmanager
    def get_connection(cls):
        if cls._connection_pool is None:
            cls.initialize_pool()
        
        conn = cls._connection_pool.getconn()
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"Database error: {e}")
            raise
        finally:
            cls._connection_pool.putconn(conn)
    
    @classmethod
    def execute_query(cls, query: str, params: Optional[Tuple] = None, fetch_one: bool = False):
        with cls.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
                return cur.fetchone() if fetch_one else cur.fetchall()
    
    @classmethod
    def execute_update(cls, query: str, params: Optional[Tuple] = None) -> int:
        with cls.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
                return cur.rowcount


class PatientDB:
    @staticmethod
    def create_patient(full_name: str, phone_number: str, 
                      preferred_language: str = 'kinyarwanda', 
                      location: Optional[str] = None) -> Dict:
        query = """
            INSERT INTO patient (full_name, phone_number, preferred_language, location)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (phone_number, full_name) 
            DO UPDATE SET updated_at = CURRENT_TIMESTAMP
            RETURNING *
        """
        with DatabaseConnection.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (full_name, phone_number, preferred_language, location))
                return dict(cur.fetchone())
    
    @staticmethod
    def get_patient_by_phone(phone_number: str) -> Optional[Dict]:
        query = "SELECT * FROM patient WHERE phone_number = %s ORDER BY created_at DESC LIMIT 1"
        return DatabaseConnection.execute_query(query, (phone_number,), fetch_one=True)
    
    @staticmethod
    def get_patient_by_id(patient_id: int) -> Optional[Dict]:
        query = "SELECT * FROM patient WHERE patient_id = %s"
        return DatabaseConnection.execute_query(query, (patient_id,), fetch_one=True)


class SessionDB:
    @staticmethod
    def create_session(patient_id: int) -> Dict:
        query = "INSERT INTO session (patient_id, status) VALUES (%s, 'active') RETURNING *"
        with DatabaseConnection.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (patient_id,))
                return dict(cur.fetchone())
    
    @staticmethod
    def get_session(session_id: int) -> Optional[Dict]:
        query = "SELECT * FROM session WHERE session_id = %s"
        return DatabaseConnection.execute_query(query, (session_id,), fetch_one=True)
    
    @staticmethod
    def update_session_status(session_id: int, status: str) -> int:
        query = "UPDATE session SET status = %s WHERE session_id = %s"
        return DatabaseConnection.execute_update(query, (status, session_id))
    
    @staticmethod
    def close_session(session_id: int) -> int:
        query = "SELECT close_session(%s)"
        with DatabaseConnection.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (session_id,))
                return 1
    
    @staticmethod
    def update_prediction_info(session_id: int, prediction_label: str, confidence: float) -> int:
        query = "UPDATE session SET prediction_label = %s, prediction_confidence = %s WHERE session_id = %s"
        return DatabaseConnection.execute_update(query, (prediction_label, confidence, session_id))
    
    @staticmethod
    def get_sessions_awaiting_review() -> List[Dict]:
        return DatabaseConnection.execute_query("SELECT * FROM v_sessions_awaiting_review")


class ConversationDB:
    @staticmethod
    def add_message(session_id: int, sender_type: str, message_text: str, 
                    sequence_number: int, metadata: Optional[Dict] = None) -> Dict:
        query = """
            INSERT INTO conversation_message 
            (session_id, sender_type, message_text, sequence_number, metadata)
            VALUES (%s, %s, %s, %s, %s) RETURNING *
        """
        metadata_json = json.dumps(metadata) if metadata else None
        with DatabaseConnection.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (session_id, sender_type, message_text, sequence_number, metadata_json))
                return dict(cur.fetchone())
    
    @staticmethod
    def get_conversation(session_id: int) -> List[Dict]:
        query = "SELECT * FROM conversation_message WHERE session_id = %s ORDER BY sequence_number"
        return DatabaseConnection.execute_query(query, (session_id,))
    
    @staticmethod
    def get_last_sequence_number(session_id: int) -> int:
        query = "SELECT COALESCE(MAX(sequence_number), 0) as last_seq FROM conversation_message WHERE session_id = %s"
        result = DatabaseConnection.execute_query(query, (session_id,), fetch_one=True)
        return result['last_seq'] if result else 0


class SymptomDB:
    @staticmethod
    def add_symptom(session_id: int, symptom_name: str, severity: Optional[str] = None, 
                    duration: Optional[str] = None, additional_info: Optional[str] = None) -> Dict:
        query = """
            INSERT INTO symptom (session_id, symptom_name, severity, duration, additional_info)
            VALUES (%s, %s, %s, %s, %s) RETURNING *
        """
        with DatabaseConnection.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (session_id, symptom_name, severity, duration, additional_info))
                return dict(cur.fetchone())
    
    @staticmethod
    def get_session_symptoms(session_id: int) -> List[Dict]:
        query = "SELECT * FROM symptom WHERE session_id = %s ORDER BY recorded_at"
        return DatabaseConnection.execute_query(query, (session_id,))


class PredictionDB:
    @staticmethod
    def create_prediction(session_id: int, predicted_condition: str, risk_level: str, 
                         confidence_score: float, model_version: Optional[str] = None) -> Dict:
        query = """
            INSERT INTO prediction (session_id, predicted_condition, risk_level, confidence_score, model_version)
            VALUES (%s, %s, %s, %s, %s) RETURNING *
        """
        with DatabaseConnection.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (session_id, predicted_condition, risk_level, confidence_score, model_version))
                return dict(cur.fetchone())
    
    @staticmethod
    def get_session_prediction(session_id: int) -> Optional[Dict]:
        query = "SELECT * FROM prediction WHERE session_id = %s"
        return DatabaseConnection.execute_query(query, (session_id,), fetch_one=True)
    
    @staticmethod
    def mark_reviewed(prediction_id: int, worker_id: int, review_notes: Optional[str] = None) -> int:
        query = """
            UPDATE prediction SET reviewed_by = %s, reviewed_at = CURRENT_TIMESTAMP, 
            review_notes = %s WHERE prediction_id = %s
        """
        return DatabaseConnection.execute_update(query, (worker_id, review_notes, prediction_id))


class PrescriptionDB:
    @staticmethod
    def create_prescription(session_id: int, worker_id: int, medication_name: str, 
                          dosage: str, instructions: str, duration: Optional[str] = None,
                          notes: Optional[str] = None) -> Dict:
        query = """
            INSERT INTO prescription (session_id, worker_id, medication_name, dosage, instructions, duration, notes)
            VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING *
        """
        with DatabaseConnection.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (session_id, worker_id, medication_name, dosage, instructions, duration, notes))
                return dict(cur.fetchone())
    
    @staticmethod
    def mark_dispensed(prescription_id: int) -> int:
        query = "UPDATE prescription SET dispensed = TRUE, dispensed_at = CURRENT_TIMESTAMP WHERE prescription_id = %s"
        return DatabaseConnection.execute_update(query, (prescription_id,))
    
    @staticmethod
    def get_session_prescription(session_id: int) -> Optional[Dict]:
        query = "SELECT * FROM prescription WHERE session_id = %s"
        return DatabaseConnection.execute_query(query, (session_id,), fetch_one=True)


class HealthcareWorkerDB:
    @staticmethod
    def get_worker(worker_id: int) -> Optional[Dict]:
        query = "SELECT * FROM healthcare_worker WHERE worker_id = %s"
        return DatabaseConnection.execute_query(query, (worker_id,), fetch_one=True)
    
    @staticmethod
    def get_worker_activity(worker_id: int) -> Optional[Dict]:
        query = "SELECT * FROM v_worker_activity WHERE worker_id = %s"
        return DatabaseConnection.execute_query(query, (worker_id,), fetch_one=True)
