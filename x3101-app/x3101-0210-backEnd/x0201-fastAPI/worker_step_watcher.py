"""
Worker: Step Watcher — Auto Advance AUTO Steps
===============================================
Polls read_telemetry() every 500ms for each plant.
When PLC current_step is in AUTO_STEPS (8, 10, 28),
automatically advances to the next step in the execution plan
without waiting for operator input.

AUTO step rules:
  Step  8 = D1010 Dissolve Tank 1  → auto-pass (pre-dissolved externally)
  Step 10 = D1030 Dissolve Tank 2  → auto-pass (pre-dissolved externally)
  Step 28 = End                    → auto-pass → reset to step 0

Gate steps (4, 14, 22, 26) and condition steps (6, 12, 16, 18, 20, 24)
are NOT auto-advanced — they require operator or physical condition.
"""

import asyncio
import logging
import struct
import time
from typing import Optional, Dict

from database import SessionLocal
from plc_service import (
    read_telemetry, read_full_actuals,
    get_db_number, plc, check_scan_bit
)

logger = logging.getLogger(__name__)

# ─── Constants ────────────────────────────────────────────────────────────────
AUTO_STEPS = {8, 10, 28}   # steps that auto-advance without operator
POLL_INTERVAL = 0.5        # seconds between polls

# ─── State ────────────────────────────────────────────────────────────────────
_running: bool = False
_task: Optional[asyncio.Task] = None

# Track last auto-advanced step per plant to prevent double-firing
_last_auto_step: Dict[int, int] = {1: -1, 2: -1, 3: -1}
# Debounce: timestamp of last advance per plant
_last_advance_ts: Dict[int, float] = {1: 0.0, 2: 0.0, 3: 0.0}
DEBOUNCE_SEC = 3.0   # min seconds between consecutive auto-advances per plant


def _get_next_step_in_plan(sku_id: str, current_step: int) -> Optional[int]:
    """
    Build execution plan for the SKU and return the next step after current_step.
    Returns None if current_step is the last step or SKU not found.
    """
    try:
        from sqlalchemy import text
        from recipe_sequencer import build_execution_sequence

        db = SessionLocal()
        try:
            rows = db.execute(text("""
                SELECT phase_number, phase_id, sub_step, master_step,
                       plc_step_no, phase_type_code, action_code, re_code,
                       step_time, temperature, temp_low, temp_high,
                       agitator_rpm, high_shear_rpm
                FROM sku_steps WHERE sku_id = :sku_id
                ORDER BY phase_number, sub_step
            """), {"sku_id": sku_id}).fetchall()

            if not rows:
                return None

            steps = [dict(r._mapping) for r in rows]
            result = build_execution_sequence(steps)
            plan = result.get("execution_plan", [])

            step_numbers = [g["plc_step"] for g in plan]
            if current_step in step_numbers:
                idx = step_numbers.index(current_step)
                if idx + 1 < len(step_numbers):
                    return step_numbers[idx + 1]
            return None

        finally:
            db.close()

    except Exception as e:
        logger.warning(f"[StepWatcher] Cannot build plan for SKU {sku_id}: {e}")
        return None


def _get_active_batch_sku(plant_id: int) -> Optional[str]:
    """
    Query DB for the active batch's SKU ID for a given plant.
    Returns None if no active batch found.
    """
    try:
        from sqlalchemy import text

        db = SessionLocal()
        try:
            row = db.execute(text("""
                SELECT sku_id FROM production_batches
                WHERE plant_id = :plant_id AND status = 'Running'
                ORDER BY created_at DESC LIMIT 1
            """), {"plant_id": plant_id}).fetchone()
            return row[0] if row else None
        finally:
            db.close()
    except Exception as e:
        logger.debug(f"[StepWatcher] Cannot get active batch plant={plant_id}: {e}")
        return None


def _do_auto_advance(plant_id: int, current_step: int, next_step: int):
    """
    Write next step to PLC: update SEQ+1 in DB15X7 and pulse Cmd_NewStep.
    Mirrors the logic of force_next_step endpoint.
    """
    try:
        db_actual = get_db_number("actual", plant_id)
        db_cmd    = get_db_number("step_command", plant_id)

        actuals = read_full_actuals(plant_id)
        current_seq = actuals.get("current_seq", 0) if actuals else 0
        next_seq    = current_seq + 1

        # Write SEQ+1 → DB15X7 offset 46 (Int, big-endian)
        plc.db_write(db_actual, 46, bytearray(struct.pack(">h", next_seq)))

        # Pulse Cmd_NewStep → DB15X0 offset 86
        plc.db_write(db_cmd, 86, bytearray([0x80]))
        time.sleep(0.15)
        plc.db_write(db_cmd, 86, bytearray([0x00]))

        logger.info(
            f"[StepWatcher] ✅ AUTO advance Plant={plant_id} "
            f"Step {current_step} → {next_step} | SEQ {current_seq}→{next_seq}"
        )

        # Log event (non-critical)
        try:
            from sqlalchemy import text
            db = SessionLocal()
            db.execute(text("""
                INSERT INTO batch_event_logs
                    (batch_id, plant_id, event_type, detail, created_at)
                VALUES (:bid, :pid, :etype, :detail, NOW())
            """), {
                "bid": actuals.get("batch_id", "-") if actuals else "-",
                "pid": plant_id,
                "etype": "AUTO_NEXT_STEP",
                "detail": f"Step {current_step}→{next_step} (auto-pass)"
            })
            db.commit()
            db.close()
        except Exception:
            pass

    except Exception as e:
        logger.error(f"[StepWatcher] ❌ Auto advance failed Plant={plant_id}: {e}")


async def _poll_step_watcher_loop(interval: float = POLL_INTERVAL):
    """
    Main polling loop — runs every `interval` seconds.
    """
    global _running, _last_auto_step, _last_advance_ts

    _running = True
    logger.info("🔍 Step Watcher started (auto-advance AUTO steps every %.1fs)", interval)

    while _running:
        try:
            for plant_id in [1, 2, 3]:
                # 1. Check SCAN bit — only act when SCAN=ON
                if not check_scan_bit(plant_id):
                    continue

                # 2. Read telemetry
                tel = read_telemetry(plant_id)
                if not tel:
                    continue

                current_step = int(tel.get("current_step", 0))

                # 3. Is this step in AUTO_STEPS?
                if current_step not in AUTO_STEPS:
                    continue

                # 4. Debounce — don't fire if we just advanced
                now = time.time()
                if (current_step == _last_auto_step[plant_id] and
                        now - _last_advance_ts[plant_id] < DEBOUNCE_SEC):
                    continue

                # 5. Get active SKU execution plan
                sku_id = _get_active_batch_sku(plant_id)
                if not sku_id:
                    logger.debug(f"[StepWatcher] Plant={plant_id} no active batch — skip")
                    continue

                next_step = _get_next_step_in_plan(sku_id, current_step)
                if next_step is None:
                    logger.warning(
                        f"[StepWatcher] Plant={plant_id} Step={current_step} "
                        f"SKU={sku_id}: no next step found"
                    )
                    continue

                # 6. Auto advance!
                logger.info(
                    f"[StepWatcher] Plant={plant_id} Step={current_step} is AUTO "
                    f"→ advancing to Step={next_step} (SKU={sku_id})"
                )
                _do_auto_advance(plant_id, current_step, next_step)
                _last_auto_step[plant_id]  = current_step
                _last_advance_ts[plant_id] = now

        except Exception as e:
            logger.error(f"[StepWatcher] Unexpected error in poll loop: {e}")

        await asyncio.sleep(interval)

    logger.info("🔍 Step Watcher stopped")


def start_step_watcher():
    """Start the background step watcher task."""
    global _task, _running
    if _task and not _task.done():
        logger.warning("[StepWatcher] Already running — skip start")
        return
    _running = True
    loop = asyncio.get_event_loop()
    _task = loop.create_task(_poll_step_watcher_loop())
    logger.info("[StepWatcher] Task created ✅")


def stop_step_watcher():
    """Stop the background step watcher task."""
    global _running, _task
    _running = False
    if _task and not _task.done():
        _task.cancel()
    logger.info("[StepWatcher] Stopped ✅")
