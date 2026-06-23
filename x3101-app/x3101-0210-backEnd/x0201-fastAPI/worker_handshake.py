"""
Worker: Handshake Poller — DB1513 Background Loop
===================================================
Polls the PLC's DB1513 (Handshake) data block every 1 second to detect
step completion events and log them to the MySQL database.

Also subscribes to MQTT step_cmd topics to log operator step commands to
the database in real-time.

Topic routing:
  Production : mixing/plant/+/step_cmd
  SIM mode   : sim/plant/+/step_cmd   (when MQTT_TOPIC_PREFIX=SIM/)

This runs as a background asyncio task inside the FastAPI application.
"""

import asyncio
import logging
import struct
import threading
from datetime import datetime
from typing import Optional, Dict

from sqlalchemy.orm import Session
from database import SessionLocal
from plc_service import read_handshake, read_telemetry, plc, get_db_number, unpack_s7_string
import paho.mqtt.publish as publish
import paho.mqtt.client as mqtt_client
import json

logger = logging.getLogger(__name__)

# ─── State Tracking ─────────────────────────────────────────────────────────
_last_finished_step: Dict[int, int] = {1: -1, 2: -1, 3: -1}
_last_batch_id: Dict[int, str] = {1: "", 2: "", 3: ""}  # track batch change per plant
_running: bool = False
_task: Optional[asyncio.Task] = None


async def _poll_handshake_loop(interval: float = 1.0):
    """
    Continuously poll DB1513, 1523, 1533 for step completion signals.
    When Step_Complete is detected, log the result to the database and clear the bit.
    """
    global _last_finished_step, _last_batch_id, _running
    _running = True
    logger.info("🔄 Handshake worker started (polling DB15x3 every %.1fs)", interval)

    while _running:
        try:
            for plant_id in [1, 2, 3]:
                # 1. Telemetry Loop
                tel = read_telemetry(plant_id)
                if tel:
                    # Reset memory if PLC step goes backward (e.g. restart or new batch)
                    current_plc_step = tel.get("current_step", 0)
                    if current_plc_step < _last_finished_step[plant_id]:
                        _last_finished_step[plant_id] = -1
                    # Publish DB1512 directly to UI bypassing Kepware
                    try:
                        import os as _os
                        _prefix = _os.getenv("MQTT_TOPIC_PREFIX", "")
                        publish.single(
                            topic=f"{_prefix}mixing/plant/{plant_id}/telemetry",
                            payload=json.dumps(tel),
                            hostname="127.0.0.1",
                            port=1883,
                            qos=0,
                            retain=False,
                            auth={'username': 'xMixingNode-1', 'password': 'x123456'}
                        )
                    except Exception as e:
                        logger.error(f"Failed to publish telemetry for Plant {plant_id}: {e}")

                # 2. Handshake Loop
                hs = read_handshake(plant_id)
                if hs is None:
                    continue  # PLC not connected or DB read failed

                # Detect batch change or PLC reset
                _hdr = plc.db_read(get_db_number('full_recipe', plant_id), 0, 20)
                if _hdr is not None:
                    _cur_bid = unpack_s7_string(_hdr, 0, 20).strip()
                    # 1. Detect if PLC batch was cleared/reset (cur_bid is empty/hyphen but last_batch_id was a valid batch)
                    if _cur_bid in ("-", "") and _last_batch_id[plant_id] and _last_batch_id[plant_id] not in ("-", ""):
                        old_bid = _last_batch_id[plant_id]
                        logger.info(f"🔄 Plant {plant_id} PLC batch cleared/reset (Batch_ID in PLC is {_cur_bid!r})")
                        from sqlalchemy import text
                        db_session = SessionLocal()
                        try:
                            # Check status of this batch in database
                            batch_row = db_session.execute(text("""
                                SELECT status FROM production_batches 
                                WHERE batch_id = :batch_id LIMIT 1
                            """), {"batch_id": old_bid}).fetchone()
                            
                            # ONLY auto-clear/reset if the batch was In-Progress (not Done / completed)
                            if batch_row and batch_row[0] == 'In-Progress':
                                logger.info(f"🗑️ [Auto-Reset] Active batch {old_bid} was reset via PLC/HMI. Clearing DB logs and resetting status to Pending.")
                                # Delete production_step_logs
                                db_session.execute(text("""
                                    DELETE FROM production_step_logs WHERE batch_id = :batch_id
                                """), {"batch_id": old_bid})
                                # Reset batch status to Pending
                                db_session.execute(text("""
                                    UPDATE production_batches 
                                    SET status = 'Pending', updated_at = NOW() 
                                    WHERE batch_id = :batch_id
                                """), {"batch_id": old_bid})
                                db_session.commit()
                        except Exception as reset_db_err:
                            logger.error(f"Failed to auto-reset batch {old_bid} in DB: {reset_db_err}")
                            db_session.rollback()
                        finally:
                            db_session.close()
                        
                        # Reset handshake tracking states
                        _last_finished_step[plant_id] = -1
                        _last_batch_id[plant_id] = ""

                    # 2. Detect batch changed (cur_bid is a valid new batch)
                    elif _cur_bid and _cur_bid not in ("-", "") and _cur_bid != _last_batch_id[plant_id]:
                        logger.info(f"🔄 Plant {plant_id} batch changed: {_last_batch_id[plant_id]!r} → {_cur_bid!r} | resetting step tracker")
                        _last_finished_step[plant_id] = -1
                        _last_batch_id[plant_id] = _cur_bid
                else:
                    # If _hdr is None (read failed / disconnected), do not treat as reset or change
                    pass

                if hs["step_complete"] and hs["finished_step"] != _last_finished_step[plant_id]:
                    step_no = hs["finished_step"]
                    _last_finished_step[plant_id] = step_no

                    logger.info(
                        f"✅ Plant {plant_id} Step {step_no} COMPLETE — "
                        f"Temp={hs['end_temp']}°C, Weight={hs['end_weight']}kg, "
                        f"Error={hs['error_flag']}"
                    )

                    # Log to database
                    await _log_step_completion(
                        plant_id=plant_id,
                        step_no=step_no,
                        end_temp=hs["end_temp"],
                        end_weight=hs["end_weight"],
                        error_flag=hs["error_flag"],
                        error_code=hs["error_code"]
                    )
                    
                    # Publish MQTT STEP_COMPLETE for frontend auto-advance
                    try:
                        mqtt_payload = {
                            "status": "STEP_COMPLETE",
                            "step_no": step_no,
                            "end_temp": hs["end_temp"],
                            "end_weight": hs["end_weight"]
                        }
                        # Publish to local Mosquitto with optional SIM prefix to avoid crossover
                        import os as _os
                        _prefix = _os.getenv("MQTT_TOPIC_PREFIX", "")
                        publish.single(f"{_prefix}mixing/plant/{plant_id}/status", payload=json.dumps(mqtt_payload), hostname="127.0.0.1", port=1883, auth={'username': 'xMixingNode-1', 'password': 'x123456'})
                        logger.info(f"📢 Published STEP_COMPLETE for Plant {plant_id} Step {step_no} (prefix='{_prefix}')")
                    except Exception as mqtt_e:
                        logger.error(f"Failed to publish STEP_COMPLETE: {mqtt_e}")
                    
                    # Acknowledge: Clear the step_complete bit in PLC
                    db_number = get_db_number('handshake', plant_id)
                    plc.db_write(db_number, 0, b'\x00')

                if hs["error_flag"]:
                    logger.warning(f"⚠️ Plant {plant_id} PLC Error detected: code={hs['error_code']}")

        except Exception as e:
            logger.error(f"Handshake poll error: {e}")

        await asyncio.sleep(interval)

    logger.info("🛑 Handshake worker stopped")


async def _log_step_completion(
    plant_id: int,
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
        await loop.run_in_executor(None, _sync_log_step, plant_id, step_no, end_temp, end_weight, error_flag, error_code)
    except Exception as e:
        logger.error(f"Failed to log step completion: {e}")


def _sync_log_step(plant_id: int, step_no: int, end_temp: float, end_weight: float, error_flag: bool, error_code: int):
    """Synchronous database write for step completion logging."""
    db: Session = SessionLocal()
    try:
        from sqlalchemy import text
        import re
        from plc_service import get_db_number, plc, unpack_s7_string, deserialize_recipe_step

        # 1. Read Batch_ID and SKU_ID from PLC's DB15x1
        db_number = get_db_number('full_recipe', plant_id)
        header = plc.db_read(db_number, 0, 52)
        
        batch_id = f"PLANT-{plant_id}-STEP-{step_no}"
        sku_id = None
        phase_id = ""
        step_log_id = step_no  # default: seq number; overridden to sub_step when matched
        action_code = ""
        re_code = ""
        target_value = 0.0

        if header:
            batch_id = unpack_s7_string(header, 0, 20)
            
        # 2. Query Batch and SKU info from App Database
        if batch_id:
            batch_row = db.execute(text("""
                SELECT sku_id FROM production_batches 
                WHERE batch_id = :batch_id LIMIT 1
            """), {"batch_id": batch_id}).fetchone()
            if batch_row:
                sku_id = batch_row[0]

        # If DB1511 batch_id is invalid/empty, skip logging to avoid writing to wrong batch
        if not sku_id or batch_id.startswith("PLANT-") or batch_id in ("-", ""):
            logger.warning(
                f"⚠️ Plant {plant_id} Step {step_no}: DB1511 has no valid batch_id ('{batch_id}'). "
                f"Load recipe first. Skipping step log."
            )
            return

        # 3. Retrieve Step Details from SkuStep (App database recipe)
        db_step_found = False
        if sku_id:
            try:
                steps_res = db.execute(text("""
                    SELECT phase_number, sub_step, phase_id, action_code, re_code, `require` 
                    FROM sku_steps WHERE sku_id = :sku_id
                """), {"sku_id": sku_id}).fetchall()
                
                if steps_res:
                    steps_list = []
                    for r in steps_res:
                        steps_list.append({
                            "phase_number": r[0],
                            "sub_step": r[1],
                            "phase_id": r[2],
                            "action_code": r[3],
                            "re_code": r[4],
                            "require": r[5]
                        })
                    
                    # Sort steps using same logic as router_plc
                    sorted_steps = sorted(steps_list, key=lambda s: (
                        int(re.sub(r'^[a-zA-Z]+', '', str(s["phase_number"] or '0').strip()) or 0),
                        s["sub_step"] or 0
                    ))
                    
                    if 0 <= (step_no - 1) < len(sorted_steps):
                        matched_step = sorted_steps[step_no - 1]
                        # Use the actual phase_id from SKU step (e.g. 'A1010', 'D1010', 'x1010')
                        # Fallback to a normalized phase_number (p010 style) if phase_id is missing
                        _pnum_raw = str(matched_step["phase_number"] or '').strip()
                        _pnum_norm = re.sub(r'^(p)(0+)', lambda m: m.group(1), _pnum_raw) if _pnum_raw else ''
                        phase_id = matched_step["phase_id"] or _pnum_norm or f"step_{step_no}"
                        step_log_id = matched_step["sub_step"] or step_no   # 10, 20, 30...
                        action_code = matched_step["action_code"] or ""
                        re_code = matched_step["re_code"] or ""
                        target_value = matched_step["require"] or 0.0
                        db_step_found = True
                        logger.info(f"Matched step {step_no} → phase_id={phase_id} sub_step={step_log_id} re_code={re_code} (SKU: {sku_id})")
            except Exception as db_err:
                logger.error(f"Failed to query step details from database: {db_err}")

        # 4. Fallback to reading step detail from PLC DB15x1 if DB query failed/returned nothing
        if not db_step_found and header:
            try:
                step_offset = 52 + (step_no - 1) * 78
                step_data = plc.db_read(db_number, step_offset, 78)
                if step_data:
                    step_detail = deserialize_recipe_step(step_data, 0)
                    phase_id = step_detail.get('phase_id', '')
                    action_code = step_detail.get('action_code', '')
                    re_code = step_detail.get('re_code', '')
                    target_value = step_detail.get('target_weight', 0.0)
                    logger.info(f"Fallback: read step {step_no} details from PLC DB15{plant_id}1")
            except Exception as plc_err:
                logger.error(f"PLC read fallback failed: {plc_err}")

        # 5. Fetch the latest active logged-in operator from App
        active_user = "System"
        try:
            user_row = db.execute(text("""
                SELECT username FROM users 
                WHERE status = 'Active' AND last_login IS NOT NULL 
                ORDER BY last_login DESC LIMIT 1
            """)).fetchone()
            if user_row:
                active_user = user_row[0]
                logger.info(f"Logged step operator2 assigned to latest login user: {active_user}")
        except Exception as user_err:
            logger.warning(f"Could not query latest active user: {user_err}")

        # Fetch recheck_by from prebatch_items for the scan user (operator)
        scan_user = active_user
        if re_code and batch_id:
            try:
                row_item = db.execute(text("""
                    SELECT recheck_by FROM prebatch_items
                    WHERE batch_id = :batch_id AND re_code = :re_code LIMIT 1
                """), {"batch_id": batch_id, "re_code": re_code}).fetchone()
                if row_item and row_item[0]:
                    scan_user = row_item[0]
                    logger.info(f"Logged step operator (scan) retrieved from prebatch_items: {scan_user}")
            except Exception as e:
                logger.warning(f"Could not query recheck_by from prebatch_items: {e}")

        # 6a. Read actual_weight from DB1517 (same source as x61-MixingControl UI display)
        #     DB1513 end_weight and DB1517 actual_weight may differ — DB1517 is the ground truth.
        actual_val = end_weight  # fallback: use handshake end_weight
        try:
            from plc_service import read_full_actuals
            actuals = read_full_actuals(plant_id)
            if actuals and actuals.get('steps'):
                # Match by step_index (sequential 1-based same as step_no)
                matched = next((s for s in actuals['steps'] if s.get('step_index') == step_no), None)
                if matched and matched.get('actual_weight') is not None:
                    actual_val = matched['actual_weight']
                    logger.info(f"📊 Plant {plant_id} Step {step_no}: actual_weight from DB1517 = {actual_val} kg (end_weight DB1513 = {end_weight} kg)")
        except Exception as db17_err:
            logger.warning(f"Could not read DB1517 actuals for step {step_no}: {db17_err} — using end_weight fallback")

        # 6b. Upsert log into production_step_logs (prevent duplicates from repeated confirms)
        db.execute(text("""
            INSERT INTO production_step_logs 
                (batch_id, phase_id, step_id, action_code, re_code, target_value, actual_value, completed_at, operator, operator2)
            VALUES 
                (:batch_id, :phase_id, :step_id, :action_code, :re_code, :target_value, :actual_value, :completed_at, :operator, :operator2)
            ON DUPLICATE KEY UPDATE
                actual_value = VALUES(actual_value),
                completed_at = VALUES(completed_at),
                operator     = VALUES(operator),
                operator2    = VALUES(operator2)
        """), {
            "batch_id": batch_id,
            "phase_id": phase_id,
            "step_id": step_log_id,  # sub_step (10/20/30) matches UI format
            "action_code": action_code,
            "re_code": re_code,
            "target_value": target_value,
            "actual_value": actual_val,  # ← DB1517 actual_weight (matches x61 display)
            "completed_at": datetime.now(),
            "operator": scan_user,
            "operator2": active_user
        })
        db.commit()
        logger.info(f"📝 Plant {plant_id} Step {step_no} logged to database (batch_id={batch_id}, operator={scan_user}, operator2={active_user})")


        # 7. Auto-complete batch when last step is done
        total_steps = struct.unpack_from('>h', header, 46)[0] if header else 0
        if total_steps > 0 and step_no >= total_steps:
            try:
                result = db.execute(text("""
                    UPDATE production_batches
                    SET status = 'Done', updated_at = NOW()
                    WHERE batch_id = :batch_id AND status = 'In-Progress'
                """), {"batch_id": batch_id})
                db.commit()
                if result.rowcount > 0:
                    logger.info(f"🏁 Batch {batch_id} auto-completed → Done ({step_no}/{total_steps} steps)")
                else:
                    logger.info(f"ℹ️ Batch {batch_id} last step done but status was not In-Progress")
            except Exception as done_err:
                logger.error(f"Failed to auto-complete batch {batch_id}: {done_err}")
                db.rollback()
    except Exception as e:
        db.rollback()
        logger.error(f"Could not log step {step_no} to DB: {e}")
    finally:
        db.close()


# ─── MQTT step_cmd Subscriber ────────────────────────────────────────────────

_mqtt_subscriber_thread: Optional[threading.Thread] = None
_mqtt_sub_client: Optional[any] = None

MQTT_HOST = "127.0.0.1"
MQTT_PORT = 1883
MQTT_USER = "xMixingNode-1"
MQTT_PASS = "x123456"
import os as _os
MQTT_PREFIX = _os.getenv("MQTT_TOPIC_PREFIX", "")  # e.g. "SIM/" for SIM mode, "" for production


def _on_step_cmd_message(client, userdata, message):
    """Handle incoming step_cmd and cmd messages."""
    try:
        topic = message.topic  # e.g. "mixing/plant/1/step_cmd" or "mixing/plant/1/cmd"
        parts = topic.split("/")
        plant_id = 1
        for i, part in enumerate(parts):
            if part == 'plant' and i + 1 < len(parts) and parts[i + 1].isdigit():
                plant_id = int(parts[i + 1])
                break

        payload_str = message.payload.decode("utf-8", errors="replace")
        payload = json.loads(payload_str)

        # ── Handle cmd topic (START / PAUSE / ABORT) ─────────────────────────
        # Writes hmi_command to BOTH:
        #   DB1511+44  (main PLC recipe header)
        #   DB1510+0   (Control Equipment PLC via PUT-GET)
        cmd = str(payload.get("command") or "").strip().upper()
        if cmd in ("START", "PAUSE", "ABORT"):
            cmd_map = {"START": 1, "PAUSE": 2, "ABORT": 0}
            hmi_val = cmd_map[cmd]
            next_val = 1 if cmd == "START" else 0

            # Write DB1511+44
            db1511 = get_db_number('full_recipe', plant_id)
            ok1 = plc.db_write(db1511, 44, struct.pack('>h', hmi_val))

            # Write DB1510+0
            db1510 = get_db_number('step_cmd', plant_id)
            ok2 = plc.db_write(db1510, 0, struct.pack('>hh', hmi_val, next_val))

            logger.info(
                f"[CMD] Plant {plant_id} | {cmd} → hmi_command={hmi_val} "
                f"| DB{db1511}+44={'OK' if ok1 else 'FAIL'} "
                f"| DB{db1510}+0={'OK' if ok2 else 'FAIL'}"
            )
            return

        # ── Handle step_cmd topic (log step details to database) ─────────────
        batch_id  = str(payload.get("Batch_ID") or "").strip()
        phase_id  = str(payload.get("Phase_ID") or payload.get("Confirm_Phase") or "").strip()
        step_id   = int(payload.get("Step_ID") or payload.get("Confirm_Step") or 0)
        action_code = str(payload.get("HMI_Command") or "").strip()
        re_code   = str(payload.get("Re_Code_ID") or "").strip()
        target_val = float(payload.get("Req_Qty") or 0)

        if not batch_id or batch_id == "-":
            logger.debug(f"step_cmd received but no valid Batch_ID, skipping DB log")
            return

        logger.info(
            f"📨 step_cmd received — Plant {plant_id} | Batch={batch_id} "
            f"| Phase={phase_id} | Step={step_id} | re_code={re_code} | qty={target_val}"
        )

        # Log to database synchronously (this runs in a thread, so sync DB is fine)
        _sync_log_step_cmd(
            batch_id=batch_id,
            phase_id=phase_id,
            step_id=step_id,
            action_code=action_code,
            re_code=re_code,
            target_value=target_val,
        )

    except Exception as e:
        logger.error(f"Error handling step_cmd/cmd message: {e}")


def _sync_log_step_cmd(
    batch_id: str,
    phase_id: str,
    step_id: int,
    action_code: str,
    re_code: str,
    target_value: float,
):
    """Write operator step command to production_step_logs."""
    db: Session = SessionLocal()
    try:
        from sqlalchemy import text

        # 1. Fetch latest active operator
        active_user = "operator"
        try:
            user_row = db.execute(text("""
                SELECT username FROM users
                WHERE status = 'Active' AND last_login IS NOT NULL
                ORDER BY last_login DESC LIMIT 1
            """)).fetchone()
            if user_row:
                active_user = user_row[0]
        except Exception:
            pass

        # 2. Query prebatch_items for recheck_by if re_code exists
        scan_user = active_user
        if re_code and batch_id:
            try:
                row_item = db.execute(text("""
                    SELECT recheck_by FROM prebatch_items
                    WHERE batch_id = :batch_id AND re_code = :re_code LIMIT 1
                """), {"batch_id": batch_id, "re_code": re_code}).fetchone()
                if row_item and row_item[0]:
                    scan_user = row_item[0]
            except Exception:
                pass

        db.execute(text("""
            INSERT INTO production_step_logs
                (batch_id, phase_id, step_id, action_code, re_code,
                 target_value, actual_value, completed_at, operator, operator2)
            VALUES
                (:batch_id, :phase_id, :step_id, :action_code, :re_code,
                 :target_value, :actual_value, :completed_at, :operator, :operator2)
        """), {
            "batch_id":    batch_id,
            "phase_id":    phase_id,
            "step_id":     step_id,
            "action_code": action_code,
            "re_code":     re_code,
            "target_value": target_value,
            "actual_value": target_value,  # will be overwritten by handshake log on completion
            "completed_at": datetime.now(),
            "operator":    scan_user,
            "operator2":   active_user,
        })
        db.commit()
        logger.info(
            f"📝 step_cmd logged — batch={batch_id} phase={phase_id} "
            f"step={step_id} re_code={re_code} operator={scan_user} operator2={active_user}"
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to log step_cmd to DB: {e}")
    finally:
        db.close()


def _start_mqtt_step_cmd_subscriber():
    """Start a background MQTT client that subscribes to all plant step_cmd topics."""
    global _mqtt_sub_client
    try:
        import random, string
        suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
        client = mqtt_client.Client(client_id=f"xmixing-step-cmd-{suffix}", clean_session=True)
        client.username_pw_set(MQTT_USER, MQTT_PASS)
        client.on_message = _on_step_cmd_message

        def on_connect(c, userdata, flags, rc):
            if rc == 0:
                import os as _os
                _prefix = _os.getenv("MQTT_TOPIC_PREFIX", "").strip("/")
                if _prefix.upper() == "SIM":
                    topics = [("sim/plant/+/step_cmd", 1), ("sim/plant/+/cmd", 1)]
                else:
                    prefix_part = f"{_prefix}/" if _prefix else ""
                    topics = [
                        (f"{prefix_part}mixing/plant/+/step_cmd", 1),
                        (f"{prefix_part}mixing/plant/+/cmd", 1),
                    ]
                c.subscribe(topics)
                topic_names = [t[0] for t in topics]
                logger.info(f"📡 step_cmd/cmd MQTT subscriber connected → {topic_names}")
            else:
                logger.error(f"step_cmd MQTT subscriber connect failed: rc={rc}")

        client.on_connect = on_connect
        client.connect(MQTT_HOST, MQTT_PORT, keepalive=60)
        _mqtt_sub_client = client
        client.loop_forever()
    except Exception as e:
        logger.error(f"step_cmd MQTT subscriber error: {e}")


# ─── MQTT MIX-xx-PUT Subscriber (App → DB1510 Interlock) ─────────────────────
# Frontend sends hmi_command and next_step_cmd every 2 seconds via heartbeat.
# This subscriber receives them and writes hmi_command directly to DB1510
# so that PLC can read the interlock state from the Data Block.
#
# DB1510 Layout (write target):
#   +0  hmi_command  Int(2)   — 1=Run, 2=HOLD (app not ready), 0=Idle
#   +2  next_step_cmd Int(2)  — 1=Allow advance, 0=Block

_put_subscriber_thread: Optional[threading.Thread] = None
_put_sub_client: Optional[any] = None


def _on_put_message(client, userdata, message):
    """Receive MIX-xx-PUT from frontend and write hmi_command to both:
      - DB1511 offset +44  (HMI_Command in recipe header — main PLC reads this)
      - DB1510 offset +0   (Control Equipment PLC reads via PUT-GET)

    DB1511 Header:  +44 HMI_Command Int(2)
    DB1510 Layout:   +0 HMI_Command Int(2), +2 next_step_cmd Int(2)
    """
    try:
        topic = message.topic
        # RabbitMQ MQTT plugin converts '/' to '.' in routing keys.
        # "MIX-01-PUT" may arrive as ".MIX-01-PUT" (leading dot) — strip it.
        topic_base = topic.split('/')[-1] if '/' in topic else topic
        topic_base = topic_base.lstrip('.').lstrip('/')  # ← strip leading . or /
        if not (topic_base.startswith('MIX-') and topic_base.endswith('-PUT')):
            return

        parts = topic.replace('/', '-').split('-')
        plant_id = 1
        for part in parts:
            if part.isdigit() and len(part) <= 2:
                plant_id = int(part)
                break

        payload_str = message.payload.decode('utf-8', errors='replace')
        payload = json.loads(payload_str)

        hmi_command   = int(payload.get('hmi_command',   2))  # Default HOLD(2), not RUN(1)
        next_step_cmd = int(payload.get('next_step_cmd', 0))

        # 1. Write to DB1511 offset +44 (main PLC — recipe header HMI_Command)
        db1511 = get_db_number('full_recipe', plant_id)
        ok1 = plc.db_write(db1511, 44, struct.pack('>h', hmi_command))

        # 2. ALSO write to DB1510 offset +0 (Control Equipment PLC via PUT-GET)
        #    Layout: +0 HMI_Command(Int16), +2 next_step_cmd(Int16)
        db1510 = get_db_number('step_cmd', plant_id)
        ok2 = plc.db_write(db1510, 0, struct.pack('>hh', hmi_command, next_step_cmd))

        logger.info(
            f"[PUT] Plant {plant_id} | hmi_command={hmi_command} next_step_cmd={next_step_cmd} "
            f"| DB{db1511}+44={'OK' if ok1 else 'FAIL'} "
            f"| DB{db1510}+0={'OK' if ok2 else 'FAIL'}"
        )

    except Exception as e:
        logger.error(f"Error handling MIX-PUT message: {e}")


def _start_mqtt_put_subscriber():
    """Start background MQTT client subscribing to MIX-xx-PUT heartbeat topics."""
    global _put_sub_client
    try:
        import random, string
        suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
        client = mqtt_client.Client(client_id=f"xmixing-put-sub-{suffix}", clean_session=True)
        client.username_pw_set(MQTT_USER, MQTT_PASS)
        client.on_message = _on_put_message

        def on_connect(c, userdata, flags, rc):
            if rc == 0:
                import os as _os
                _prefix = _os.getenv('MQTT_TOPIC_PREFIX', '').strip('/')
                # MIX-xx-PUT uses dash separators, not slash — must subscribe broadly
                # and filter in _on_put_message by topic name
                if _prefix:
                    topic = f"{_prefix}/#"
                else:
                    topic = "#"
                c.subscribe(topic, qos=0)
                logger.info(f"📡 MIX-PUT subscriber connected → subscribed to '{topic}' (filtering MIX-*-PUT)")
            else:
                logger.error(f"MIX-PUT subscriber connect failed: rc={rc}")

        client.on_connect = on_connect
        client.connect(MQTT_HOST, MQTT_PORT, keepalive=60)
        _put_sub_client = client
        client.loop_forever()
    except Exception as e:
        logger.error(f"MIX-PUT subscriber error: {e}")


# ─── Public API ──────────────────────────────────────────────────────────────

def start_handshake_worker():
    """Start the background handshake polling task and MQTT subscribers."""
    global _task, _mqtt_subscriber_thread, _put_subscriber_thread
    if _task is not None and not _task.done():
        logger.info("Handshake worker is already running")
        return

    loop = asyncio.get_event_loop()
    _task = loop.create_task(_poll_handshake_loop())
    logger.info("🚀 Handshake worker task created")

    # Start MQTT step_cmd subscriber (logs step commands to DB)
    if _mqtt_subscriber_thread is None or not _mqtt_subscriber_thread.is_alive():
        _mqtt_subscriber_thread = threading.Thread(
            target=_start_mqtt_step_cmd_subscriber,
            daemon=True,
            name="mqtt-step-cmd-sub"
        )
        _mqtt_subscriber_thread.start()
        logger.info("🚀 MQTT step_cmd subscriber thread started")

    # Start MQTT MIX-PUT subscriber (writes hmi_command to DB1510 for PLC interlock)
    if _put_subscriber_thread is None or not _put_subscriber_thread.is_alive():
        _put_subscriber_thread = threading.Thread(
            target=_start_mqtt_put_subscriber,
            daemon=True,
            name="mqtt-put-sub"
        )
        _put_subscriber_thread.start()
        logger.info("🚀 MQTT MIX-PUT subscriber thread started (interlock → DB1510)")


def stop_handshake_worker():
    """Stop the background handshake polling task and MQTT subscribers."""
    global _running, _task, _mqtt_sub_client, _put_sub_client
    _running = False
    if _task:
        _task.cancel()
        _task = None
    if _mqtt_sub_client:
        try:
            _mqtt_sub_client.disconnect()
        except Exception:
            pass
        _mqtt_sub_client = None
    if _put_sub_client:
        try:
            _put_sub_client.disconnect()
        except Exception:
            pass
        _put_sub_client = None
    logger.info("Handshake worker stop requested")
