"""
Authentication Router
=====================
Handles user login and registration endpoints.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import logging

import crud
import schemas
from database import get_db
from auth import create_access_token, verify_password

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/login")
def login(request: schemas.LoginRequest, db: Session = Depends(get_db)):
    """Authenticate user and return JWT token."""
    # Find user by email or username
    db_user = crud.get_user_by_email(db, email=request.username_or_email)
    if not db_user:
        db_user = crud.get_user_by_username(db, username=request.username_or_email)
    
    if not db_user or not verify_password(request.password, db_user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    # Update last login
    try:
        db_user.last_login = datetime.now()
        db.commit()
    except Exception:
        db.rollback()
        logger.warning("Failed to update last login timestamp")
    
    # Create JWT token
    access_token = create_access_token(
        data={
            "sub": db_user.email,
            "user_id": db_user.id,
            "username": db_user.username,
            "role": db_user.role,
            "permissions": db_user.permissions or []
        },
        expires_delta=timedelta(hours=8)
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": db_user.id,
            "username": db_user.username,
            "email": db_user.email,
            "full_name": db_user.full_name,
            "role": db_user.role,
            "department": db_user.department,
            "status": db_user.status,
            "permissions": db_user.permissions or []
        }
    }


@router.post("/verify")
def verify_user_password(request: schemas.LoginRequest, db: Session = Depends(get_db)):
    """Verify user password without returning a token."""
    db_user = crud.get_user_by_email(db, email=request.username_or_email)
    if not db_user:
        db_user = crud.get_user_by_username(db, username=request.username_or_email)
    
    if not db_user or not verify_password(request.password, db_user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid password")
    
    return {"status": "success"}


@router.post("/register", response_model=schemas.User, status_code=201)
def register(user: schemas.UserCreate, db: Session = Depends(get_db)):
    """Register a new user account."""
    if crud.get_user_by_username(db, username=user.username):
        raise HTTPException(status_code=400, detail="Username already registered")
    if crud.get_user_by_email(db, email=user.email):
        raise HTTPException(status_code=400, detail="Email already registered")
    
    if not user.role:
        user.role = "Operator"
    
    return crud.create_user(db=db, user=user)
