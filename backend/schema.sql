CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TYPE language_preference AS ENUM ('kinyarwanda', 'english');
CREATE TYPE worker_role AS ENUM ('doctor', 'nurse', 'clinician');
CREATE TYPE session_status AS ENUM ('active', 'awaiting_review', 'completed');
CREATE TYPE sender_type AS ENUM ('patient', 'ml_system');
CREATE TYPE severity_level AS ENUM ('mild', 'moderate', 'severe');
CREATE TYPE risk_level AS ENUM ('low', 'medium', 'high');

CREATE TABLE patient (
    patient_id SERIAL PRIMARY KEY,
    full_name VARCHAR(255) NOT NULL,
    phone_number VARCHAR(20) NOT NULL,
    preferred_language language_preference DEFAULT 'kinyarwanda',
    location VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    CONSTRAINT patient_phone_check CHECK (phone_number ~ '^[0-9+\-\(\) ]+$'),
    CONSTRAINT patient_name_length CHECK (LENGTH(TRIM(full_name)) >= 2)
);

CREATE INDEX idx_patient_phone ON patient(phone_number);
CREATE INDEX idx_patient_name ON patient(full_name);
CREATE INDEX idx_patient_created_at ON patient(created_at DESC);
CREATE UNIQUE INDEX idx_patient_phone_name ON patient(phone_number, full_name);

CREATE TABLE healthcare_worker (
    worker_id SERIAL PRIMARY KEY,
    full_name VARCHAR(255) NOT NULL,
    role worker_role NOT NULL,
    specialization VARCHAR(255),
    facility VARCHAR(255),
    contact_info VARCHAR(255),
    is_active BOOLEAN DEFAULT TRUE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    CONSTRAINT worker_name_length CHECK (LENGTH(TRIM(full_name)) >= 2)
);

CREATE INDEX idx_worker_role ON healthcare_worker(role);
CREATE INDEX idx_worker_facility ON healthcare_worker(facility);
CREATE INDEX idx_worker_active ON healthcare_worker(is_active) WHERE is_active = TRUE;

CREATE TABLE session (
    session_id SERIAL PRIMARY KEY,
    patient_id INTEGER NOT NULL,
    start_time TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    end_time TIMESTAMP WITH TIME ZONE,
    status session_status DEFAULT 'active' NOT NULL,
    prediction_label VARCHAR(255),
    prediction_confidence NUMERIC(5,4),
    notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    CONSTRAINT fk_session_patient FOREIGN KEY (patient_id) 
        REFERENCES patient(patient_id) ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT session_time_check CHECK (end_time IS NULL OR end_time >= start_time),
    CONSTRAINT session_confidence_range CHECK (prediction_confidence IS NULL OR 
        (prediction_confidence >= 0 AND prediction_confidence <= 1))
);

CREATE INDEX idx_session_patient ON session(patient_id);
CREATE INDEX idx_session_status ON session(status);
CREATE INDEX idx_session_start_time ON session(start_time DESC);
CREATE INDEX idx_session_patient_status ON session(patient_id, status);

CREATE TABLE conversation_message (
    message_id SERIAL PRIMARY KEY,
    session_id INTEGER NOT NULL,
    sender_type sender_type NOT NULL,
    message_text TEXT NOT NULL,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    sequence_number INTEGER NOT NULL,
    metadata JSONB,
    CONSTRAINT fk_message_session FOREIGN KEY (session_id) 
        REFERENCES session(session_id) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT message_text_not_empty CHECK (LENGTH(TRIM(message_text)) > 0),
    CONSTRAINT message_sequence_positive CHECK (sequence_number > 0)
);

CREATE INDEX idx_message_session ON conversation_message(session_id);
CREATE INDEX idx_message_timestamp ON conversation_message(timestamp);
CREATE INDEX idx_message_session_sequence ON conversation_message(session_id, sequence_number);
CREATE UNIQUE INDEX idx_message_session_sequence_unique ON conversation_message(session_id, sequence_number);

CREATE TABLE symptom (
    symptom_id SERIAL PRIMARY KEY,
    session_id INTEGER NOT NULL,
    symptom_name VARCHAR(255) NOT NULL,
    severity severity_level,
    duration VARCHAR(100),
    additional_info TEXT,
    recorded_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    CONSTRAINT fk_symptom_session FOREIGN KEY (session_id) 
        REFERENCES session(session_id) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT symptom_name_not_empty CHECK (LENGTH(TRIM(symptom_name)) > 0)
);

CREATE INDEX idx_symptom_session ON symptom(session_id);
CREATE INDEX idx_symptom_name ON symptom(symptom_name);
CREATE INDEX idx_symptom_severity ON symptom(severity);

CREATE TABLE prediction (
    prediction_id SERIAL PRIMARY KEY,
    session_id INTEGER NOT NULL,
    predicted_condition VARCHAR(255) NOT NULL,
    risk_level risk_level NOT NULL,
    confidence_score NUMERIC(5,4) NOT NULL,
    model_version VARCHAR(50),
    generated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    reviewed_by INTEGER,
    reviewed_at TIMESTAMP WITH TIME ZONE,
    review_notes TEXT,
    CONSTRAINT fk_prediction_session FOREIGN KEY (session_id) 
        REFERENCES session(session_id) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT fk_prediction_reviewer FOREIGN KEY (reviewed_by) 
        REFERENCES healthcare_worker(worker_id) ON DELETE SET NULL ON UPDATE CASCADE,
    CONSTRAINT prediction_confidence_range CHECK (confidence_score >= 0 AND confidence_score <= 1),
    CONSTRAINT prediction_review_time_check CHECK (reviewed_at IS NULL OR reviewed_at >= generated_at)
);

CREATE INDEX idx_prediction_session ON prediction(session_id);
CREATE INDEX idx_prediction_condition ON prediction(predicted_condition);
CREATE INDEX idx_prediction_risk ON prediction(risk_level);
CREATE INDEX idx_prediction_reviewer ON prediction(reviewed_by);
CREATE UNIQUE INDEX idx_prediction_session_unique ON prediction(session_id);

CREATE TABLE prescription (
    prescription_id SERIAL PRIMARY KEY,
    session_id INTEGER NOT NULL,
    worker_id INTEGER NOT NULL,
    medication_name VARCHAR(255) NOT NULL,
    dosage VARCHAR(255) NOT NULL,
    instructions TEXT NOT NULL,
    duration VARCHAR(100),
    prescribed_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    dispensed BOOLEAN DEFAULT FALSE,
    dispensed_at TIMESTAMP WITH TIME ZONE,
    notes TEXT,
    CONSTRAINT fk_prescription_session FOREIGN KEY (session_id) 
        REFERENCES session(session_id) ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_prescription_worker FOREIGN KEY (worker_id) 
        REFERENCES healthcare_worker(worker_id) ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT prescription_medication_not_empty CHECK (LENGTH(TRIM(medication_name)) > 0),
    CONSTRAINT prescription_dosage_not_empty CHECK (LENGTH(TRIM(dosage)) > 0),
    CONSTRAINT prescription_instructions_not_empty CHECK (LENGTH(TRIM(instructions)) > 0)
);

CREATE INDEX idx_prescription_session ON prescription(session_id);
CREATE INDEX idx_prescription_worker ON prescription(worker_id);
CREATE INDEX idx_prescription_medication ON prescription(medication_name);
CREATE INDEX idx_prescription_prescribed_at ON prescription(prescribed_at DESC);
CREATE INDEX idx_prescription_dispensed ON prescription(dispensed) WHERE dispensed = FALSE;

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_patient_updated_at BEFORE UPDATE ON patient
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_healthcare_worker_updated_at BEFORE UPDATE ON healthcare_worker
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_session_updated_at BEFORE UPDATE ON session
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE VIEW v_session_overview AS
SELECT 
    s.session_id, s.start_time, s.end_time, s.status,
    p.patient_id, p.full_name AS patient_name, p.phone_number, p.preferred_language,
    pred.predicted_condition, pred.risk_level, pred.confidence_score,
    pr.prescription_id, pr.medication_name,
    hw.full_name AS prescriber_name, hw.role AS prescriber_role
FROM session s
JOIN patient p ON s.patient_id = p.patient_id
LEFT JOIN prediction pred ON s.session_id = pred.session_id
LEFT JOIN prescription pr ON s.session_id = pr.session_id
LEFT JOIN healthcare_worker hw ON pr.worker_id = hw.worker_id;

CREATE VIEW v_sessions_awaiting_review AS
SELECT 
    s.session_id, s.start_time,
    p.full_name AS patient_name, p.phone_number,
    pred.predicted_condition, pred.risk_level, pred.confidence_score,
    COUNT(DISTINCT sym.symptom_id) AS symptom_count,
    COUNT(DISTINCT cm.message_id) AS message_count
FROM session s
JOIN patient p ON s.patient_id = p.patient_id
LEFT JOIN prediction pred ON s.session_id = pred.session_id
LEFT JOIN symptom sym ON s.session_id = sym.session_id
LEFT JOIN conversation_message cm ON s.session_id = cm.session_id
WHERE s.status = 'awaiting_review'
GROUP BY s.session_id, s.start_time, p.full_name, p.phone_number, 
         pred.predicted_condition, pred.risk_level, pred.confidence_score
ORDER BY s.start_time ASC;

CREATE VIEW v_worker_activity AS
SELECT 
    hw.worker_id, hw.full_name, hw.role, hw.facility,
    COUNT(DISTINCT pr.prescription_id) AS total_prescriptions,
    COUNT(DISTINCT pred.prediction_id) AS total_reviews,
    MAX(pr.prescribed_at) AS last_prescription_date,
    MAX(pred.reviewed_at) AS last_review_date
FROM healthcare_worker hw
LEFT JOIN prescription pr ON hw.worker_id = pr.worker_id
LEFT JOIN prediction pred ON hw.worker_id = pred.reviewed_by
WHERE hw.is_active = TRUE
GROUP BY hw.worker_id, hw.full_name, hw.role, hw.facility;

CREATE OR REPLACE FUNCTION close_session(p_session_id INTEGER)
RETURNS VOID AS $$
BEGIN
    UPDATE session 
    SET status = 'completed', end_time = CURRENT_TIMESTAMP
    WHERE session_id = p_session_id AND status != 'completed';
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION get_patient_history(p_patient_id INTEGER)
RETURNS TABLE (
    session_id INTEGER,
    start_time TIMESTAMP WITH TIME ZONE,
    predicted_condition VARCHAR(255),
    risk_level risk_level,
    prescribed BOOLEAN
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        s.session_id, s.start_time,
        pred.predicted_condition, pred.risk_level,
        (pr.prescription_id IS NOT NULL) AS prescribed
    FROM session s
    LEFT JOIN prediction pred ON s.session_id = pred.session_id
    LEFT JOIN prescription pr ON s.session_id = pr.session_id
    WHERE s.patient_id = p_patient_id
    ORDER BY s.start_time DESC;
END;
$$ LANGUAGE plpgsql;
