"""
routers/auth.py — Authentication and authorization endpoints.

POST /auth/login       → authenticate user, return JWT token
POST /auth/register    → register new user (platform admin only)
GET  /auth/me          → get current user info from token
"""

import os
from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr
import bcrypt
import jwt

from database.database import UserDB, DatabaseConnection

# Initialize database connection pool
try:
    DatabaseConnection.initialize_pool()
except:
    pass  # May already be initialized

router = APIRouter(prefix="/auth", tags=["authentication"])
security = HTTPBearer()

# JWT settings
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-secret-key-change-this-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    role: str  # platform_admin, hospital_admin, doctor
    facility_id: Optional[int] = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    user: dict


class UserResponse(BaseModel):
    user_id: int
    email: str
    full_name: str
    role: str
    facility_id: Optional[int]
    is_active: bool


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=12)).decode()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode(), hashed_password.encode())


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def decode_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired"
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    """Dependency to get current user from JWT token"""
    token = credentials.credentials
    payload = decode_token(token)
    user_id = payload.get("user_id")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload"
        )
    
    user = UserDB.get_user_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )
    
    if not user['is_active']:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive"
        )
    
    return dict(user)


def require_role(*allowed_roles: str):
    """Dependency factory for role-based access control"""
    def role_checker(user: dict = Depends(get_current_user)) -> dict:
        if user['role'] not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required role: {', '.join(allowed_roles)}"
            )
        return user
    return role_checker


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/login", response_model=TokenResponse)
def login(request: LoginRequest):
    """Authenticate user and return JWT token"""
    user = UserDB.get_user_by_email(request.email)
    
    if not user or not verify_password(request.password, user['password_hash']):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )
    
    if not user['is_active']:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive"
        )
    
    access_token = create_access_token(
        data={"user_id": user['user_id'], "email": user['email'], "role": user['role']}
    )
    
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        user={
            "user_id": user['user_id'],
            "email": user['email'],
            "full_name": user['full_name'],
            "role": user['role'],
            "facility_id": user['facility_id']
        }
    )


@router.post("/register", response_model=UserResponse)
def register(
    request: RegisterRequest,
    current_user: dict = Depends(require_role("platform_admin"))
):
    """Register a new user (platform admin only)"""
    # Check if user already exists
    existing_user = UserDB.get_user_by_email(request.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Validate role
    valid_roles = ['platform_admin', 'hospital_admin', 'doctor']
    if request.role not in valid_roles:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid role. Must be one of: {', '.join(valid_roles)}"
        )
    
    # Hash password and create user
    hashed_password = hash_password(request.password)
    user = UserDB.create_user(
        email=request.email,
        password_hash=hashed_password,
        full_name=request.full_name,
        role=request.role,
        facility_id=request.facility_id
    )
    
    return UserResponse(
        user_id=user['user_id'],
        email=user['email'],
        full_name=user['full_name'],
        role=user['role'],
        facility_id=user['facility_id'],
        is_active=user['is_active']
    )


@router.get("/me", response_model=UserResponse)
def get_me(current_user: dict = Depends(get_current_user)):
    """Get current user information from token"""
    return UserResponse(
        user_id=current_user['user_id'],
        email=current_user['email'],
        full_name=current_user['full_name'],
        role=current_user['role'],
        facility_id=current_user['facility_id'],
        is_active=current_user['is_active']
    )
