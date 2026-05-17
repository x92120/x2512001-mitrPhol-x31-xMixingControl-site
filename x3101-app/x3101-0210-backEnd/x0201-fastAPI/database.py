"""
Database Configuration Module
=============================
SQLAlchemy database connection setup for MySQL/MariaDB.
Connects to the Cloud DB (152.42.166.150).

Environment Variables:
- DB_USER: Database username
- DB_PASSWORD: Database password
- DB_HOST: Database host address
- DB_PORT: Database port (default: 3306)
- DB_NAME: Database name
- CLOUD_DB: Cloud database host
"""

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
import logging
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

logger = logging.getLogger(__name__)

# =============================================================================
# DATABASE CONFIGURATION
# =============================================================================

DB_USER = os.getenv("DB_USER", "mixingcontrol")
DB_PASSWORD = os.getenv("DB_PASSWORD", "admin100")
DB_PORT = os.getenv("DB_PORT", "3306")
DB_NAME = os.getenv("DB_NAME", "xMixingControl")

# Database host — Prefer .env DB_HOST, then CLOUD_DB, then default to remote IP
DB_HOST = os.getenv("DB_HOST", os.getenv("CLOUD_DB", "192.168.121.11"))


def _build_url(host: str, timeout: int = 3) -> str:
    return f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{host}:{DB_PORT}/{DB_NAME}?connect_timeout={timeout}"


def _create_engine_for(host: str, timeout: int = 3):
    url = _build_url(host, timeout)
    return create_engine(
        url,
        pool_pre_ping=True,       # Validate connections before use (avoids stale conn errors)
        pool_recycle=1800,         # Recycle connections every 30 min (MySQL default wait_timeout=28800s)
        pool_size=10,              # Maintain 10 persistent connections
        max_overflow=20,           # Allow up to 30 total under load
        pool_timeout=10,           # Wait max 10s for a connection from the pool
    )


# Engine and session
engine = _create_engine_for(DB_HOST)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for declarative models
Base = declarative_base()


def get_active_db_info() -> dict:
    """Return info about the active database."""
    return {
        "key": "cloudDB",
        "label": "Cloud DB",
        "host": DB_HOST,
        "icon": "cloud",
    }


# Dependency for Cloud
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Engine and session for Locally Dockerized Buffer DB
LOCAL_DB_HOST = os.getenv("LOCAL_DB_HOST", "127.0.0.1")

# ── Local DB Health Check ────────────────────────────────────────────────────
# Cache the local DB availability to avoid blocking requests with 5s timeouts
# when the local MariaDB is not running.
import time as _time
_local_db_last_check = 0.0
_local_db_available = False
_LOCAL_DB_CHECK_INTERVAL = 30  # Re-check every 30 seconds

def _check_local_db() -> bool:
    """Quick TCP probe to see if local DB is reachable (non-blocking, 1s timeout)."""
    global _local_db_last_check, _local_db_available
    now = _time.time()
    if now - _local_db_last_check < _LOCAL_DB_CHECK_INTERVAL:
        return _local_db_available
    _local_db_last_check = now
    import socket
    try:
        sock = socket.create_connection((LOCAL_DB_HOST, int(DB_PORT)), timeout=1)
        sock.close()
        _local_db_available = True
        logger.info("Local edge DB is reachable at %s:%s", LOCAL_DB_HOST, DB_PORT)
    except (socket.timeout, ConnectionRefusedError, OSError):
        _local_db_available = False
        logger.warning("Local edge DB is NOT reachable at %s:%s — skipping", LOCAL_DB_HOST, DB_PORT)
    return _local_db_available


# Only create the engine if local DB is reachable (lazy init)
_local_engine = None
_LocalSessionLocal = None

def _get_local_engine():
    global _local_engine, _LocalSessionLocal
    if _local_engine is None:
        _local_engine = _create_engine_for(LOCAL_DB_HOST, timeout=2)
        _LocalSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_local_engine)
    return _local_engine

def _get_local_session_maker():
    global _LocalSessionLocal
    if _LocalSessionLocal is None:
        _get_local_engine()
    return _LocalSessionLocal


# Dependency for Edge Buffer Db
def get_local_db():
    if not _check_local_db():
        raise ConnectionError("Local edge DB is not reachable")
    session_maker = _get_local_session_maker()
    db = session_maker()
    try:
        yield db
    finally:
        db.close()
