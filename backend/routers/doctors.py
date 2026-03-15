"""
routers/doctors.py — Doctor management endpoints for hospital admins.

POST   /doctors                        → register a new doctor
GET    /doctors                        → list doctors at the admin's facility
GET    /doctors/{doctor_id}            → get a doctor's profile
PUT    /doctors/{doctor_id}            → update doctor info
PATCH  /doctors/{doctor_id}/deactivate → deactivate a doctor (soft delete)
PATCH  /doctors/{doctor_id}/activate   → reactivate a doctor

hospital_admin: can only manage doctors within their own facility.
platform_admin: can manage doctors across all facilities.
"""

from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel, EmailStr

from database.database import UserDB, FacilityDB, DatabaseConnection
from routers.auth import get_current_user, require_role, hash_password

try:
    DatabaseConnection.initialize_pool()
except Exception:
    pass

router = APIRouter(prefix="/doctors", tags=["doctors"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class DoctorRegisterRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    specialty: Optional[str] = None   # e.g. "generalist", "dentist", "pediatrician"
    facility_id: Optional[int] = None  # hospital_admin uses their own; platform_admin must supply


class DoctorUpdateRequest(BaseModel):
    full_name: Optional[str] = None
    email: Optional[EmailStr] = None
    specialty: Optional[str] = None


class DoctorResponse(BaseModel):
    user_id: int
    email: str
    full_name: str
    specialty: Optional[str]
    facility_id: Optional[int]
    is_active: bool


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _assert_facility_access(current_user: dict, target_facility_id: Optional[int]):
    """Raise 403 if a hospital_admin tries to access a doctor outside their facility."""
    if current_user['role'] == 'hospital_admin':
        if target_facility_id != current_user['facility_id']:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")


def _get_doctor_or_404(doctor_id: int) -> dict:
    user = UserDB.get_user_by_id(doctor_id)
    if not user or user['role'] != 'doctor':
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Doctor not found")
    return dict(user)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("", response_model=DoctorResponse, status_code=status.HTTP_201_CREATED)
def register_doctor(
    request: DoctorRegisterRequest,
    current_user: dict = Depends(require_role("hospital_admin", "platform_admin"))
):
    """Register a new doctor. hospital_admin registers doctors for their own facility."""
    if current_user['role'] == 'hospital_admin':
        facility_id = current_user['facility_id']
        if facility_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Your admin account is not linked to a facility"
            )
        if request.facility_id is not None and request.facility_id != facility_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only register doctors for your own facility"
            )
    else:
        # platform_admin
        if request.facility_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="facility_id is required"
            )
        facility_id = request.facility_id
        if not FacilityDB.get_facility(facility_id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Facility {facility_id} not found"
            )

    if UserDB.get_user_by_email(request.email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )

    user = UserDB.create_user(
        email=request.email,
        password_hash=hash_password(request.password),
        full_name=request.full_name,
        role="doctor",
        facility_id=facility_id,
        specialty=request.specialty,
    )
    return DoctorResponse(**user)


@router.get("", response_model=list[DoctorResponse])
def list_doctors(
    current_user: dict = Depends(require_role("hospital_admin", "platform_admin"))
):
    """List doctors. hospital_admin sees only their facility's doctors."""
    if current_user['role'] == 'hospital_admin':
        facility_id = current_user['facility_id']
        if facility_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Your admin account is not linked to a facility"
            )
        doctors = UserDB.get_doctors_by_facility(facility_id)
    else:
        doctors = UserDB.get_all_doctors()
    return [DoctorResponse(**d) for d in doctors]


@router.get("/{doctor_id}", response_model=DoctorResponse)
def get_doctor(
    doctor_id: int,
    current_user: dict = Depends(require_role("hospital_admin", "platform_admin"))
):
    """Get a single doctor's profile."""
    user = _get_doctor_or_404(doctor_id)
    _assert_facility_access(current_user, user.get('facility_id'))
    return DoctorResponse(**user)


@router.put("/{doctor_id}", response_model=DoctorResponse)
def update_doctor(
    doctor_id: int,
    request: DoctorUpdateRequest,
    current_user: dict = Depends(require_role("hospital_admin", "platform_admin"))
):
    """Update a doctor's full_name, email, or specialty."""
    user = _get_doctor_or_404(doctor_id)
    _assert_facility_access(current_user, user.get('facility_id'))

    updates = {k: v for k, v in request.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No fields to update")

    if 'email' in updates:
        existing = UserDB.get_user_by_email(updates['email'])
        if existing and existing['user_id'] != doctor_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already in use by another account"
            )

    UserDB.update_user(doctor_id, **updates)
    return DoctorResponse(**UserDB.get_user_by_id(doctor_id))


@router.patch("/{doctor_id}/deactivate", response_model=DoctorResponse)
def deactivate_doctor(
    doctor_id: int,
    current_user: dict = Depends(require_role("hospital_admin", "platform_admin"))
):
    """Deactivate a doctor (soft delete — they cannot log in but data is preserved)."""
    user = _get_doctor_or_404(doctor_id)
    _assert_facility_access(current_user, user.get('facility_id'))

    if not user['is_active']:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Doctor is already inactive")

    UserDB.update_user(doctor_id, is_active=False)
    return DoctorResponse(**UserDB.get_user_by_id(doctor_id))


@router.patch("/{doctor_id}/activate", response_model=DoctorResponse)
def activate_doctor(
    doctor_id: int,
    current_user: dict = Depends(require_role("hospital_admin", "platform_admin"))
):
    """Reactivate a previously deactivated doctor."""
    user = _get_doctor_or_404(doctor_id)
    _assert_facility_access(current_user, user.get('facility_id'))

    if user['is_active']:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Doctor is already active")

    UserDB.update_user(doctor_id, is_active=True)
    return DoctorResponse(**UserDB.get_user_by_id(doctor_id))
