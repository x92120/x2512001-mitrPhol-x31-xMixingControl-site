"""
Authentication Router
=====================
Handles user login and registration endpoints with fuzzy and flexible username matching.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timedelta
import logging
import difflib

import crud
import schemas
import models
from database import get_db
from auth import create_access_token, verify_password

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["Authentication"])


def find_user(db: Session, identifier: str):
    """Helper to find user by email, username, or full_name with robust fuzzy matching."""
    if not identifier:
        return None
    raw_val = identifier.strip()
    if raw_val.startswith('@'):
        raw_val = raw_val[1:].strip()
    if not raw_val:
        return None

    # 1. Exact matches (Email, Username, Full Name)
    user = crud.get_user_by_email(db, email=raw_val)
    if user:
        return user
    user = crud.get_user_by_username(db, username=raw_val)
    if user:
        return user
    user = db.query(models.User).filter(models.User.full_name == raw_val).first()
    if user:
        return user

    # 2. Case-insensitive exact matches
    user = db.query(models.User).filter(func.lower(models.User.email) == raw_val.lower()).first()
    if user:
        return user
    user = db.query(models.User).filter(func.lower(models.User.username) == raw_val.lower()).first()
    if user:
        return user
    user = db.query(models.User).filter(func.lower(models.User.full_name) == raw_val.lower()).first()
    if user:
        return user

    # 3. Normalized string matching (ignore spaces, dots, dashes, and normalize 'tch' <-> 'ch')
    def normalize(s: str) -> str:
        if not s:
            return ""
        return s.strip().lower().replace(' ', '').replace('.', '').replace('-', '').replace('_', '').replace('tch', 'ch')

    val_norm = normalize(raw_val)
    all_users = db.query(models.User).all()
    
    for u in all_users:
        if normalize(u.username) == val_norm or normalize(u.full_name or '') == val_norm or (u.email and normalize(u.email.split('@')[0]) == val_norm):
            return u

    # 4. Partial substring matching (e.g. 'Ratchapol' matching 'Ratchapol R.')
    for u in all_users:
        u_norm_user = normalize(u.username)
        u_norm_full = normalize(u.full_name or '')
        if val_norm and (val_norm in u_norm_user or val_norm in u_norm_full or u_norm_user in val_norm or u_norm_full in val_norm):
            return u

    # 5. Fuzzy ratio matching (Levenshtein distance ratio >= 0.70)
    best_user = None
    best_score = 0.0
    for u in all_users:
        candidates = [u.username, u.full_name or '', (u.email or '').split('@')[0]]
        for cand in candidates:
            score1 = difflib.SequenceMatcher(None, raw_val.lower(), cand.lower()).ratio()
            score2 = difflib.SequenceMatcher(None, val_norm, normalize(cand)).ratio()
            score = max(score1, score2)
            if score > best_score:
                best_score = score
                best_user = u

    if best_score >= 0.70:
        logger.info(f"Fuzzy match '{raw_val}' -> user '{best_user.username}' (score={best_score:.2f})")
        return best_user

    return None


@router.post("/login")
def login(request: schemas.LoginRequest, db: Session = Depends(get_db)):
    """Authenticate user and return JWT token. Allows passwordless login for operators/users without password."""
    db_user = find_user(db, request.username_or_email)
    
    if not db_user:
        raise HTTPException(status_code=401, detail="User not found or invalid credentials")
    
    # If password is provided, verify it if password hash exists
    if request.password and db_user.password_hash:
        if not verify_password(request.password, db_user.password_hash):
            raise HTTPException(status_code=401, detail="Invalid credentials")
    # If no password is provided, passwordless login is granted (Option A)
    
    # Update last login
    try:
        db_user.last_login = datetime.now()
        db.commit()
    except Exception:
        db.rollback()
        logger.warning("Failed to update last login timestamp")
    
    role_str = db_user.role.value if hasattr(db_user.role, 'value') else str(db_user.role)
    status_str = db_user.status.value if hasattr(db_user.status, 'value') else str(db_user.status)

    # Create JWT token
    access_token = create_access_token(
        data={
            "sub": db_user.email,
            "user_id": db_user.id,
            "username": db_user.username,
            "role": role_str,
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
            "role": role_str,
            "department": db_user.department,
            "status": status_str,
            "permissions": db_user.permissions or []
        }
    }


@router.post("/verify")
def verify_user_password(request: schemas.LoginRequest, db: Session = Depends(get_db)):
    """Verify user password without returning a token."""
    db_user = find_user(db, request.username_or_email)
    if not db_user:
        raise HTTPException(status_code=401, detail="Invalid password")
    
    if request.password and db_user.password_hash:
        if not verify_password(request.password, db_user.password_hash):
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


@router.post("/badge-login")
def badge_login(request: schemas.BadgeLoginRequest, db: Session = Depends(get_db)):
    """QR Badge login – authenticate directly via auto-scan without PIN (Option A)."""
    db_user = find_user(db, request.username)
    if not db_user:
        raise HTTPException(status_code=401, detail="Badge not recognized")
    
    status_val = db_user.status.value if hasattr(db_user.status, 'value') else str(db_user.status)
    if status_val == 'Inactive':
        raise HTTPException(status_code=403, detail="Account is inactive")
    
    # If PIN was provided and user has a PIN configured, verify it
    if request.badge_pin and db_user.badge_pin_hash:
        if not verify_password(request.badge_pin, db_user.badge_pin_hash):
            logger.warning(f"Failed badge login PIN for user: {request.username}")
            raise HTTPException(status_code=401, detail="Invalid badge PIN")
    
    # Update last login
    try:
        db_user.last_login = datetime.now()
        db.commit()
    except Exception:
        db.rollback()
    
    role_str = db_user.role.value if hasattr(db_user.role, 'value') else str(db_user.role)

    access_token = create_access_token(
        data={
            "sub": db_user.email,
            "user_id": db_user.id,
            "username": db_user.username,
            "role": role_str,
            "permissions": db_user.permissions or []
        },
        expires_delta=timedelta(hours=8)
    )
    
    logger.info(f"Badge login success (auto scan): {db_user.username}")
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": db_user.id,
            "username": db_user.username,
            "email": db_user.email,
            "full_name": db_user.full_name,
            "role": role_str,
            "department": db_user.department,
            "status": status_val,
            "permissions": db_user.permissions or []
        }
    }


@router.post("/switch-operator/{username}")
def switch_operator(username: str, db: Session = Depends(get_db)):
    """Update last_login of a user when switching operators on the front-end."""
    db_user = find_user(db, username)
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    try:
        db_user.last_login = datetime.now()
        db.commit()
        logger.info(f"Operator switched to: {username} (updated last_login)")
        return {"status": "success", "username": username}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
