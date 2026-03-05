"""
routers/queue.py — Examination queue management endpoints.

GET    /queue                         → get queue for facility
GET    /queue/{queue_id}              → get queue entry details
POST   /queue/{queue_id}/assign       → assign patient to doctor/room
PUT    /queue/{queue_id}/status       → update queue status
GET    /queue/doctor/me               → get queue for current doctor
"""

from typing import Optional, List
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel

from database.database import QueueDB, SessionDB, DatabaseConnection
from routers.auth import get_current_user, require_role

# Initialize database connection pool
try:
    DatabaseConnection.initialize_pool()
except:
    pass

router = APIRouter(prefix="/queue", tags=["queue"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class AssignQueueRequest(BaseModel):
    doctor_id: int
    room_id: Optional[int] = None
    required_exams: Optional[List[str]] = None
    notes: Optional[str] = None


class UpdateStatusRequest(BaseModel):
    status: str  # waiting, in_progress, completed, cancelled


class QueueEntryResponse(BaseModel):
    queue_id: int
    queue_number: int
    queue_status: str
    patient_name: str
    phone_number: Optional[str]
    risk_level: Optional[str]
    predicted_condition: Optional[str]
    doctor_name: Optional[str]
    room_name: Optional[str]
    facility_name: str
    created_at: str
    started_at: Optional[str]
    completed_at: Optional[str]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("", response_model=list[QueueEntryResponse])
def get_facility_queue(
    status: Optional[str] = Query(None, description="Filter by status"),
    current_user: dict = Depends(require_role("doctor", "hospital_admin", "platform_admin"))
):
    """
    Get queue for the current user's facility.
    Platform admin must specify facility_id as query param.
    """
    facility_id = current_user.get('facility_id')
    
    if not facility_id:
        raise HTTPException(status_code=400, detail="User not assigned to a facility")
    
    queue = QueueDB.get_facility_queue(facility_id, status)
    return [QueueEntryResponse(**entry) for entry in queue]


@router.get("/{queue_id}", response_model=QueueEntryResponse)
def get_queue_entry(
    queue_id: int,
    current_user: dict = Depends(get_current_user)
):
    """Get queue entry details"""
    entry = QueueDB.get_queue_entry(queue_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Queue entry not found")
    
    return QueueEntryResponse(**entry)


@router.post("/{queue_id}/assign")
def assign_queue_entry(
    queue_id: int,
    request: AssignQueueRequest,
    current_user: dict = Depends(require_role("doctor", "hospital_admin"))
):
    """
    Assign a patient to a doctor and room with required exams.
    Doctors can assign to themselves, hospital admins can assign to any doctor.
    """
    entry = QueueDB.get_queue_entry(queue_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Queue entry not found")
    
    # Doctors can only assign to themselves
    if current_user['role'] == 'doctor':
        # Find worker_id from user
        from database.database import HealthcareWorkerDB
        worker = HealthcareWorkerDB.get_worker(request.doctor_id)
        if not worker or worker.get('user_id') != current_user['user_id']:
            raise HTTPException(status_code=403, detail="Doctors can only assign patients to themselves")
    
    QueueDB.assign_to_doctor(
        queue_id=queue_id,
        doctor_id=request.doctor_id,
        room_id=request.room_id,
        exams=request.required_exams,
        notes=request.notes
    )
    
    return {"message": "Patient assigned successfully", "queue_entry": QueueDB.get_queue_entry(queue_id)}


@router.put("/{queue_id}/status")
def update_queue_status(
    queue_id: int,
    request: UpdateStatusRequest,
    current_user: dict = Depends(require_role("doctor", "hospital_admin"))
):
    """Update queue entry status"""
    entry = QueueDB.get_queue_entry(queue_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Queue entry not found")
    
    valid_statuses = ['waiting', 'in_progress', 'completed', 'cancelled']
    if request.status not in valid_statuses:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status. Must be one of: {', '.join(valid_statuses)}"
        )
    
    QueueDB.update_queue_status(queue_id, request.status)
    return {"message": "Queue status updated", "queue_entry": QueueDB.get_queue_entry(queue_id)}


@router.get("/doctor/me", response_model=list[QueueEntryResponse])
def get_my_queue(current_user: dict = Depends(require_role("doctor"))):
    """Get queue for the current doctor"""
    # Get worker_id from user_id
    from database.database import HealthcareWorkerDB
    with DatabaseConnection.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT worker_id FROM healthcare_worker WHERE user_id = %s", (current_user['user_id'],))
            result = cur.fetchone()
            if not result:
                raise HTTPException(status_code=404, detail="Worker profile not found for this user")
            worker_id = result['worker_id']
    
    queue = QueueDB.get_doctor_queue(worker_id)
    return [QueueEntryResponse(**entry) for entry in queue]
