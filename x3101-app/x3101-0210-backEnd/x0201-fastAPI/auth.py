"""
Authentication Module
=====================
Handles JWT token creation/validation and password hashing for user authentication.

Environment Variables:
- SECRET_KEY: JWT signing key (required in production)
"""

from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
import os
import warnings
import bcrypt

# =============================================================================
# JWT CONFIGURATION
# =============================================================================

SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-this-in-production-xMixing2025")
if SECRET_KEY == "your-secret-key-change-this-in-production-xMixing2025":
    warnings.warn("WARNING: Using default SECRET_KEY. Set SECRET_KEY environment variable in production!")

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 480  # 8 hours

# =============================================================================
# PASSWORD FUNCTIONS
# =============================================================================


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against its hash using direct bcrypt."""
    try:
        # Bcrypt requires bytes for both password and hash
        password_bytes = plain_password.encode('utf-8')
        hash_bytes = hashed_password.encode('utf-8')
        return bcrypt.checkpw(password_bytes, hash_bytes)
    except Exception as e:
        print(f"Error verifying password: {e}")
        return False

def get_password_hash(password: str) -> str:
    """Hash a password using direct bcrypt."""
    # Bcrypt produces bytes; we decode back to string for db storage
    password_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode('utf-8')

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def decode_access_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None
