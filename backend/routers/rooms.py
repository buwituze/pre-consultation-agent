"""
routers/rooms.py — Room management endpoints.

GET    /rooms                     → list rooms (by facility)
POST   /rooms                     → create new room
GET    /rooms/{id}                → get room details
PUT    /rooms/{id}                → update room
DELETE /rooms/{id}                → delete room
PUT    /rooms/{id}/status         → update room status (active/inactive)
"""

from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel

from database.database import RoomDB, FacilityDB, DatabaseConnection
from routers.auth import get_current_user, require_role

# Initialize database connection pool
try:
    DatabaseConnection.initialize_pool()
except:
    pass

router = APIRouter(prefix="/rooms", tags=["rooms"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class RoomCreate(BaseModel):
    facility_id: int
    room_name: str
    room_type: str
    floor_number: Optional[int] = None
    capacity: int = 1


class RoomUpdate(BaseModel):
    room_name: Optional[str] = None
    room_type: Optional[str] = None
    status: Optional[str] = None  # active, inactive, maintenance
    floor_number: Optional[int] = None
    capacity: Optional[int] = None


class RoomStatusUpdate(BaseModel):
    status: str  # active, inactive, maintenance


class RoomResponse(BaseModel):
    room_id: int
    facility_id: int
    room_name: str
    room_type: str
    status: str
    floor_number: Optional[int]
    capacity: int


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("", response_model=list[RoomResponse])
def list_rooms(
    facility_id: Optional[int] = Query(None, description="Filter by facility ID"),
    status: Optional[str] = Query(None, description="Filter by status"),
    current_user: dict = Depends(get_current_user)
):
    """
    List rooms. Filters by facility_id if provided.
    Hospital admins and doctors see their facility's rooms.
    Platform admins see all or filtered rooms.
    """
    # If user is not platform admin, restrict to their facility
    if current_user['role'] != 'platform_admin':
        if not current_user['facility_id']:
            raise HTTPException(status_code=403, detail="User not assigned to a facility")
        facility_id = current_user['facility_id']
    
    if not facility_id:
        raise HTTPException(status_code=400, detail="facility_id is required")
    
    if status == 'active':
        rooms = RoomDB.get_active_rooms(facility_id)
    else:
        rooms = RoomDB.get_rooms_by_facility(facility_id)
        if status:
            rooms = [r for r in rooms if r['status'] == status]
    
    return [RoomResponse(**r) for r in rooms]


@router.post("", response_model=RoomResponse)
def create_room(
    room: RoomCreate,
    current_user: dict = Depends(require_role("platform_admin", "hospital_admin"))
):
    """Create a new room. Platform admin or hospital admin only."""
    # Hospital admin can only create rooms in their facility
    if current_user['role'] == 'hospital_admin':
        if current_user['facility_id'] != room.facility_id:
            raise HTTPException(status_code=403, detail="Can only create rooms in your facility")
    
    # Verify facility exists
    facility = FacilityDB.get_facility(room.facility_id)
    if not facility:
        raise HTTPException(status_code=404, detail="Facility not found")
    
    new_room = RoomDB.create_room(
        facility_id=room.facility_id,
        room_name=room.room_name,
        room_type=room.room_type,
        floor_number=room.floor_number,
        capacity=room.capacity
    )
    return RoomResponse(**new_room)


@router.get("/{room_id}", response_model=RoomResponse)
def get_room(
    room_id: int,
    current_user: dict = Depends(get_current_user)
):
    """Get room details by ID"""
    room = RoomDB.get_room(room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    
    # Check access permissions
    if current_user['role'] != 'platform_admin':
        if current_user['facility_id'] != room['facility_id']:
            raise HTTPException(status_code=403, detail="Access denied")
    
    return RoomResponse(**room)


@router.put("/{room_id}", response_model=RoomResponse)
def update_room(
    room_id: int,
    updates: RoomUpdate,
    current_user: dict = Depends(require_role("platform_admin", "hospital_admin"))
):
    """Update room details"""
    room = RoomDB.get_room(room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    
    # Hospital admin can only update rooms in their facility
    if current_user['role'] == 'hospital_admin':
        if current_user['facility_id'] != room['facility_id']:
            raise HTTPException(status_code=403, detail="Can only update rooms in your facility")
    
    update_data = {k: v for k, v in updates.dict().items() if v is not None}
    if update_data:
        RoomDB.update_room(room_id, **update_data)
    
    return RoomResponse(**RoomDB.get_room(room_id))


@router.put("/{room_id}/status", response_model=RoomResponse)
def update_room_status(
    room_id: int,
    status_update: RoomStatusUpdate,
    current_user: dict = Depends(require_role("hospital_admin"))
):
    """Update room status. Hospital admin only."""
    room = RoomDB.get_room(room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    
    if current_user['facility_id'] != room['facility_id']:
        raise HTTPException(status_code=403, detail="Can only update rooms in your facility")
    
    valid_statuses = ['active', 'inactive', 'maintenance']
    if status_update.status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {', '.join(valid_statuses)}")
    
    RoomDB.update_room(room_id, status=status_update.status)
    return RoomResponse(**RoomDB.get_room(room_id))


@router.delete("/{room_id}")
def delete_room(
    room_id: int,
    current_user: dict = Depends(require_role("platform_admin", "hospital_admin"))
):
    """Delete a room"""
    room = RoomDB.get_room(room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    
    # Hospital admin can only delete rooms in their facility
    if current_user['role'] == 'hospital_admin':
        if current_user['facility_id'] != room['facility_id']:
            raise HTTPException(status_code=403, detail="Can only delete rooms in your facility")
    
    RoomDB.delete_room(room_id)
    return {"message": "Room deleted successfully"}
