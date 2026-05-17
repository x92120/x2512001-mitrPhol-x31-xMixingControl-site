"""
Worker: Handshake Poller — DB1513 Background Loop
===================================================
Polls the PLC's DB1513 (Handshake) data block every 1 second to detect
step completion events and log them to the MySQL database.

This runs as a background asyncio task inside the FastAPI application.
"""

import asyncio
import logging
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session
from database import SessionLocal
from plc_service import read_handshake, plc

logger = logging.getLogger(__name__)

# ─── State Tracking ─────────────────────────────────────────────────────────
_last_finished_step: int = -1
_running: bool = False
_task: Optional[asyncio.Task] = None


async def _poll_handshake_loop(interval: float = 1.0):
    """
    Continuously poll DB1513 for step completion signals.
    When Step_Complete is detected, log the result to the database.
    """
    global _last_finished_step, _running
    _running = True
    logger.info("🔄 Handshake worker started (polling DB1513 every %.1fs)", interval)

    while _running:
        try:
            hs = read_handshake()
            if hs is None:
                # PLC not connected — wait and retry
                await asyncio.sleep(interval * 3)
                continue

            if hs["step_complete"] and hs["finished_step"] != _last_finished_step:
                step_no = hs["finished_step"]
                _last_finished_step = step_no

                logger.info(
                    f"✅ Step {step_no} COMPLETE — "
                    f"Temp={hs['end_temp']}°C, Weight={hs['end_weight']}kg, "
                    f"Error={hs['error_flag']}"
                )

                # Log to database
                await _log_step_completion(
                    step_no=step_no,
                    end_temp=hs["end_temp"],
                    end_weight=hs["end_weight"],
                    error_flag=hs["error_flag"],
                    error_code=hs["error_code"]
                )

            if hs["error_flag"]:
                logger.warning(f"⚠️ PLC Error detected: code={hs['error_code']}")

        except Exception as e:
            logger.error(f"Handshake poll error: {e}")

        await asyncio.sleep(interval)

    logger.info("🛑 Handshake worker stopped")


async def _log_step_completion(
    step_no: int,
    end_temp: float,
    end_weight: float,
    error_flag: bool,
    error_code: int
):
    """
    Write step completion data to the production_step_logs table.
    Uses a synchronous DB session in an executor to avoid blocking asyncio.
    """
    try:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _sync_log_step, step_no, end_temp, end_weight, error_flag, error_code)
    except Exception as e:
        logger.error(f"Failed to log step completion: {e}")


def _sync_log_step(step_no: int, end_temp: float, end_weight: float, error_flag: bool, error_code: int):
    """Synchronous database write for step completion logging."""
    db: Session = SessionLocal()
    try:
        from sqlalchemy import text
        db.execute(text("""
            INSERT INTO production_step_logs 
                (step_no, end_temp, end_weight, error_flag, error_code, completed_at)
            VALUES 
                (:step_no, :end_temp, :end_weight, :error_flag, :error_code, :completed_at)
        """), {
            "step_no": step_no,
            "end_temp": end_temp,
            "end_weight": end_weight,
            "error_flag": error_flag,
            "error_code": error_code,
            "completed_at": datetime.now()
        })
        db.commit()
        logger.info(f"📝 Step {step_no} logged to database")
    except Exception as e:
        db.rollback()
        # Table may not exist yet — log gracefully
        logger.warning(f"Could not log step {step_no} to DB (table may not exist): {e}")
    finally:
        db.close()


# ─── Public API ──────────────────────────────────────────────────────────────

def start_handshake_worker():
    """Start the background handshake polling task."""
    global _task
    if _task is not None and not _task.done():
        logger.info("Handshake worker is already running")
        return
    
    loop = asyncio.get_event_loop()
    _task = loop.create_task(_poll_handshake_loop())
    logger.info("🚀 Handshake worker task created")


def stop_handshake_worker():
    """Stop the background handshake polling task."""
    global _running, _task
    _running = False
    if _task:
        _task.cancel()
        _task = None
    logger.info("Handshake worker stop requested")
