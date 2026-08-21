"""
PLC Router — Recipe Data for S7-1200
=====================================
Endpoints to build and serve PLC recipe payloads for DB 1780.
"""

from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy.orm import Session
from database import get_db
import models
from plc_datablock import build_recipe_payload
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/plc", tags=["PLC"])


@router.get("/recipe/{batch_id}")
def get_recipe_for_plc(batch_id: str, db: Session = Depends(get_db)):
    """
    Build a PLC-ready recipe payload (DB 1780) for the given batch.

    Looks up the batch → plan → SKU → SKU steps, then serializes
    into the 32-process × 8-step datablock structure.
    """
    # 1. Find the batch and plan in a single optimized JOIN query
    result = db.query(models.ProductionBatch, models.ProductionPlan).join(
        models.ProductionPlan, models.ProductionBatch.plan_id == models.ProductionPlan.id
    ).filter(
        models.ProductionBatch.batch_id == batch_id
    ).first()
    
    if not result:
        raise HTTPException(status_code=404, detail=f"Batch '{batch_id}' or associated Plan not found")
        
    batch, plan = result

    # 3. Fetch SKU steps
    sku_steps = db.query(models.SkuStep).filter(
        models.SkuStep.sku_id == plan.sku_id
    ).all()

    if not sku_steps:
        raise HTTPException(
            status_code=404,
            detail=f"No SKU steps found for SKU '{plan.sku_id}'"
        )

    # Fetch prebatch items or requirements to determine the WH (Warehouse) of each re_code
    prebatch_items = db.query(models.PreBatchItem).filter(
        models.PreBatchItem.batch_id == batch_id
    ).all()
    
    wh_map = {}
    for item in prebatch_items:
        if item.re_code:
            wh_map[item.re_code.strip()] = (item.wh or "").strip().upper()
            
    # If any re_code in sku_steps is not in wh_map, look up from Ingredient table
    missing_re_codes = [s.re_code for s in sku_steps if s.re_code and s.re_code.strip() not in wh_map]
    if missing_re_codes:
        ingredients = db.query(models.Ingredient).filter(
            models.Ingredient.re_code.in_(missing_re_codes)
        ).all()
        for ing in ingredients:
            if ing.re_code:
                wh_map[ing.re_code.strip()] = (ing.warehouse or "").strip().upper()

    # 4. Convert ORM objects to dicts
    step_dicts = []
    for s in sku_steps:
        re_code_clean = str(s.re_code or "").strip()
        wh_val = wh_map.get(re_code_clean, "")
        is_mix = wh_val in ("MIX", "MIXING")
        
        step_dicts.append({
            "phase_number": s.phase_number,
            "phase_id": s.phase_id,
            "sub_step": s.sub_step,
            "master_step": s.master_step,
            "action": s.action,
            "action_code": s.action_code,
            "re_code": s.re_code,
            "setup_step": s.setup_step,
            "destination": s.destination,
            "require": s.require,
            "uom": s.uom,
            "low_tol": s.low_tol,
            "high_tol": s.high_tol,
            "step_condition": s.step_condition,
            "agitator_rpm": 0.0 if is_mix else s.agitator_rpm,
            "high_shear_rpm": 0.0 if is_mix else s.high_shear_rpm,
            "temperature": s.temperature,
            "temp_low": s.temp_low,
            "temp_high": s.temp_high,
            "step_time": s.step_time,
            "step_timer_control": s.step_timer_control,
            "qc_temp": s.qc_temp,
            "record_steam_pressure": s.record_steam_pressure,
            "record_ctw": s.record_ctw,
            "operation_brix_record": s.operation_brix_record,
            "operation_ph_record": s.operation_ph_record,
            "brix_sp": s.brix_sp,
            "ph_sp": s.ph_sp,
        })

    # 5. Extract plant ID from plan_id (format: Pyymmdd-BatchNo-PlantID)
    parts = (plan.plan_id or "").split("-")
    plant_id = parts[2] if len(parts) >= 3 else "1"

    # 6. Build the DB 1780 payload
    payload = build_recipe_payload(
        plan_id=plan.plan_id,
        batch_id=batch.batch_id,
        sku_id=plan.sku_id,
        sku_name=plan.sku_name or "",
        plant_id=plant_id,
        batch_size=batch.batch_size or 0.0,
        sku_steps=step_dicts,
    )

    logger.info(f"Built recipe for batch={batch_id}, "
                f"SKU={plan.sku_id}, "
                f"processes={payload['Header']['ProcessCount']}, "
                f"total_steps={len(step_dicts)}")

    return payload


@router.post("/send-recipe/{batch_id}")
def send_recipe_to_plc(batch_id: str, plant_id: int = 1, db: Session = Depends(get_db)):
    """
    Send recipe to the real Siemens S7-1200 PLC directly via DB1511.
    """
    import re
    # Ensure plant_id is valid (must be 1, 2, or 3)
    if plant_id not in [1, 2, 3]:
        logger.warning(f"Invalid plant_id {plant_id} received. Defaulting to 1.")
        plant_id = 1
        
    # 1. Fetch the batch and plan in a single query
    result = db.query(models.ProductionBatch, models.ProductionPlan).join(
        models.ProductionPlan, models.ProductionBatch.plan_id == models.ProductionPlan.id
    ).filter(
        models.ProductionBatch.batch_id == batch_id
    ).first()
    
    if not result:
        raise HTTPException(status_code=404, detail=f"Batch '{batch_id}' or associated Plan not found")
        
    batch, plan = result

    # 2. Fetch SKU steps
    sku_steps = db.query(models.SkuStep).filter(
        models.SkuStep.sku_id == plan.sku_id
    ).all()

    if not sku_steps:
        raise HTTPException(
            status_code=404,
            detail=f"No SKU steps found for SKU '{plan.sku_id}'"
        )

    # 3. Sort steps by phase number then sub_step to align with array seq
    sorted_steps = sorted(sku_steps, key=lambda s: (
        int(re.sub(r'^[a-zA-Z]+', '', str(s.phase_number or '0').strip()) or 0),
        s.sub_step or 0
    ))

    # Fetch prebatch items or requirements to determine the WH (Warehouse) of each re_code
    prebatch_items = db.query(models.PreBatchItem).filter(
        models.PreBatchItem.batch_id == batch_id
    ).all()
    
    wh_map = {}
    for item in prebatch_items:
        if item.re_code:
            wh_map[item.re_code.strip()] = (item.wh or "").strip().upper()
            
    # If any re_code in sorted_steps is not in wh_map, look up from Ingredient table
    missing_re_codes = [s.re_code for s in sorted_steps if s.re_code and s.re_code.strip() not in wh_map]
    if missing_re_codes:
        ingredients = db.query(models.Ingredient).filter(
            models.Ingredient.re_code.in_(missing_re_codes)
        ).all()
        for ing in ingredients:
            if ing.re_code:
                wh_map[ing.re_code.strip()] = (ing.warehouse or "").strip().upper()

    # Convert to UDT layout steps
    step_dicts = []
    for idx, s in enumerate(sorted_steps):
        phase_no_val = int(re.sub(r'^[a-zA-Z]+', '', str(s.phase_number or '0').strip()) or 0)
        re_code_clean = str(s.re_code or "").strip()
        wh_val = wh_map.get(re_code_clean, "")
        is_mix = wh_val in ("MIX", "MIXING")
        
        step_dicts.append({
            "seq": idx + 1,
            "phase_no": phase_no_val,
            "sub_step": s.sub_step or 0,
            "action_code": str(s.action_code or s.action or "")[:10],
            "phase_id": str(s.phase_id or "")[:10],
            "re_code": str(s.re_code or "")[:20],
            "target_weight": float(s.require or 0.0),
            "temp_sp": float(s.temperature or 0.0),
            "temp_low": float(s.temp_low or 0.0),
            "temp_high": float(s.temp_high or 0.0),
            "agitator_sp": 0.0 if is_mix else float(s.agitator_rpm or 0.0),
            "highshear_sp": 0.0 if is_mix else float(s.high_shear_rpm or 0.0),
            "step_time": int(s.step_time or 0)
        })

    # 4. Write to the real hardware PLC using snap7 direct write
    try:
        from plc_service import write_full_recipe_to_plc, read_recipe_from_plc, get_db_number
        
        db_full_recipe = get_db_number('full_recipe', plant_id)
        logger.info(f"Writing recipe to real PLC (DB{db_full_recipe}) for batch {batch_id} (plant {plant_id})...")
        success = write_full_recipe_to_plc(
            batch_id=batch.batch_id,
            sku_id=plan.sku_id,
            steps=step_dicts,
            plant_id=plant_id
        )
        if not success:
            raise HTTPException(
                status_code=502,
                detail=f"Real hardware communication failed: snap7 write to DB{db_full_recipe} returned False (check PLC connection)"
            )
            
        # 5. Read back for verification
        verify_data = read_recipe_from_plc(db_full_recipe)
        if not verify_data:
            raise HTTPException(status_code=502, detail=f"Failed to read back from DB{db_full_recipe} for verification.")
            
        if verify_data["batch_id"] != batch.batch_id or verify_data["total_steps"] != len(step_dicts):
            raise HTTPException(status_code=502, detail=f"Verification mismatch! Expected {len(step_dicts)} steps for {batch.batch_id}, got {verify_data['total_steps']} steps for {verify_data['batch_id']}.")
            
        logger.info(f"Successfully wrote and verified recipe to real PLC for batch {batch_id}!")
        
        # --- Hybrid Approach: Publish to MQTT for Node-RED / Remote Debugging ---
        try:
            import json, os as _os
            import paho.mqtt.publish as publish
            _prefix = _os.getenv("MQTT_TOPIC_PREFIX", "")
            mqtt_topic = f"{_prefix}MPL/PLC/Plant{plant_id}/Recipe_Sync"
            mqtt_payload = {
                "batch_id": batch.batch_id,
                "sku_id": plan.sku_id,
                "plant_id": plant_id,
                "total_steps": len(step_dicts),
                "steps": step_dicts
            }
            publish.single(mqtt_topic, payload=json.dumps(mqtt_payload), hostname="127.0.0.1", port=1883,
                           auth={'username': 'xMixingNode-1', 'password': 'x123456'})
            logger.info(f"📢 Published recipe JSON to MQTT topic: {mqtt_topic} for Node-RED")
        except Exception as mqtt_e:
            logger.error(f"Failed to publish recipe to MQTT: {mqtt_e}")

        # 6. Auto-update batch status → In-Progress so handshake worker can find it
        try:
            from sqlalchemy import text as _text
            db.execute(_text("""
                UPDATE production_batches
                SET status = 'In-Progress', updated_at = NOW()
                WHERE batch_id = :batch_id AND status NOT IN ('Done', 'Cancelled')
            """), {"batch_id": batch.batch_id})
            db.commit()
            logger.info(f"✅ Batch {batch.batch_id} status → In-Progress")
        except Exception as status_err:
            logger.warning(f"Could not update batch status: {status_err}")
            db.rollback()
            
    except Exception as e:
        logger.error(f"Failed to write recipe to real PLC: {e}")
        raise HTTPException(
            status_code=502,
            detail=f"Real hardware communication failed: snap7 error: {str(e)}"
        )

    # ── P2: Save local cache for emergency fallback (DB DOWN scenario) ────────
    try:
        from batch_cache_service import save_batch_cache
        save_batch_cache(batch.batch_id, {
            "batch_id": batch.batch_id,
            "sku_id": plan.sku_id,
            "plant_id": plant_id,
            "total_steps": len(step_dicts),
            "steps": step_dicts,
        })
    except Exception as cache_err:
        logger.warning(f"[BatchCache] non-critical save error: {cache_err}")
    # ────────────────────────────────────────────────────────────────────────────

    return {
        "status": "success",
        "message": f"Recipe successfully written and verified on real PLC for batch {batch_id}",
        "verification": {
            "batch_id": batch.batch_id,
            "sku_id": plan.sku_id,
            "total_steps": len(step_dicts),
            "verified": True
        }
    }


# =============================================================================
# DB100: STEP COMMAND (App ➔ PLC)
# =============================================================================

from plc_interface import DB1510StepCommand, DB1512Telemetry

@router.post("/step-command")
def send_step_command(command: DB1510StepCommand, db: Session = Depends(get_db)):
    """
    Push a new step command/setpoint to the PLC (DB1510).
    Also logs this step to production_step_logs for Production Report.
    """
    logger.info(f"Received Step Command: {command.Step_ID} for Batch {command.Batch_ID}")

    # Log step to database for Production Report traceability
    try:
        from sqlalchemy import text as _text
        
        # 1. Fetch latest active operator
        active_user = "operator"
        try:
            user_row = db.execute(_text("""
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
        re_code = str(getattr(command, "Re_Code_ID", "") or "").strip()
        batch_id = getattr(command, "Batch_ID", "") or ""
        if re_code and batch_id:
            try:
                row_item = db.execute(_text("""
                    SELECT recheck_by FROM prebatch_items
                    WHERE batch_id = :batch_id AND re_code = :re_code LIMIT 1
                """), {"batch_id": batch_id, "re_code": re_code}).fetchone()
                if row_item and row_item[0]:
                    scan_user = row_item[0]
            except Exception:
                pass

        db.execute(_text("""
            INSERT INTO production_step_logs 
                (batch_id, phase_id, step_id, action_code, re_code, target_value, actual_value, completed_at, operator, operator2)
            VALUES 
                (:batch_id, :phase_id, :step_id, :action_code, :re_code, :target_value, :actual_value, :completed_at, :operator, :operator2)
        """), {
            "batch_id": batch_id,
            "phase_id": str(getattr(command, "Phase_ID", "") or ""),
            "step_id": int(getattr(command, "Step_ID", 0) or 0),
            "action_code": str(getattr(command, "HMI_Command", "") or ""),
            "re_code": re_code,
            "target_value": float(getattr(command, "Req_Qty", 0) or 0),
            "actual_value": float(getattr(command, "Req_Qty", 0) or 0),
            "completed_at": datetime.now(),
            "operator": scan_user,
            "operator2": active_user,
        })
        db.commit()
        logger.info(f"Step log saved for batch={command.Batch_ID} phase={getattr(command, 'Phase_ID', '')} step={command.Step_ID} operator={scan_user} operator2={active_user}")
        
        try:
            from worker_handshake import check_and_complete_batch
            check_and_complete_batch(db, batch_id)
        except Exception as complete_err:
            logger.warning(f"Could not check batch completion in step command: {complete_err}")
    except Exception as log_err:
        logger.warning(f"Could not save step log: {log_err}")
        db.rollback()

    return {
        "status": "success",
        "timestamp": datetime.now(),
        "command_sent": command
    }


# =============================================================================
# DB200: TELEMETRY (PLC ➔ App)
# =============================================================================

# Global storage for last known telemetry (simulating live state)
_last_telemetry = DB1512Telemetry()

@router.get("/telemetry", response_model=DB1512Telemetry)
def get_plc_telemetry():
    """
    Get the latest telemetry data from the PLC (DB1512).
    Values come from MQTT bridge or background S7 polling.
    """
    global _last_telemetry
    
    # In a real environment, this might query Redis or a live cache
    return _last_telemetry

@router.post("/telemetry/update")
def update_plc_telemetry(data: DB1512Telemetry):
    """
    Endpoint for MQTT-bridge or worker to push latest PLC state (DB1512).
    """
    global _last_telemetry
    _last_telemetry = data
    _last_telemetry.Last_Update = datetime.now()
    return {"status": "updated"}

from plc_service import read_recipe_from_plc, read_full_actuals




# Cache for last known telemetry per plant (prevents UI dropout on slow reads)
_telem_cache: dict = {}

@router.get("/plant/{plant_id}/telemetry-live")
def get_plant_telemetry_live(plant_id: str = Path(..., description="Plant ID: 1, 2, or 3")):
    """
    Read live telemetry from DB15x2 (S7 PUT-GET from PLC) directly via snap7.
    Returns actual Temp, Weight, Agitator, HighShear, PH, Brix, Hopper.
    Frontend polls this every 500ms to display ACT values without MQTT latency.
    """
    import time as _time
    from plc_service import read_telemetry
    pid = int(plant_id)
    t0 = _time.time()
    data = read_telemetry(pid)
    elapsed_ms = (_time.time() - t0) * 1000
    if data is None:
        # Return last cached value to prevent UI dropout
        cached = _telem_cache.get(pid)
        if cached:
            cached["cached"] = True
            return cached
        return {"error": "PLC read failed", "plant_id": pid}
    result = {
        "plant_id":        pid,
        "mix_tank_temp":   data.get("MixTank_Temp",   0.0),
        "mix_tank_weight": data.get("MixTank_Weight", 0.0),
        "agitator_act":    data.get("Agitator_Act",   0.0),
        "highshear_act":   data.get("HighShear_Act",  0.0),
        "ph_actual":       data.get("PH_Actual",      0.0),
        "brix_actual":     data.get("Brix_Actual",    0.0),
        "hopper_weight":   data.get("Hopper_Weight",  0.0),
        "current_step":    data.get("Current_Step",   0),
        "step_timer":      data.get("Step_Timer",     0),
        "read_ms":         round(elapsed_ms, 1),
    }
    _telem_cache[pid] = result
    return result

@router.get("/plant/{plant_id}/recipe-status")
def get_plant_recipe_status(plant_id: str, db: Session = Depends(get_db)):
    """
    Read the Recipe (Target) and Actual Results directly from the PLC via snap7 based on plant_id.
    Also returns free_scan_progress: pending FH/SPP prebatch items for server-crash restore.
    """
    try:
        from plc_service import get_db_number
        from sqlalchemy import text as sa_text
        recipe_db = get_db_number('full_recipe', int(plant_id))

        target = read_recipe_from_plc(recipe_db)
        actual = read_full_actuals(int(plant_id))

        # ── Free-Scan Restore: check pending FH/SPP prebatch items ─────────
        # Used when server crashes mid Free-Scan so operator can resume scanning
        free_scan_progress = None
        batch_id = (actual or {}).get("batch_id", "")
        if batch_id and batch_id not in ("-", ""):
            try:
                rows = db.execute(sa_text("""
                    SELECT
                        pi.id,
                        pi.re_code,
                        pi.wh,
                        pi.status,
                        COUNT(ps.id) AS scanned_count,
                        pi.require
                    FROM prebatch_items pi
                    LEFT JOIN prebatch_scans ps ON ps.item_id = pi.id
                    WHERE pi.batch_id = :bid
                      AND pi.wh IN ('FH','SPP')
                    GROUP BY pi.id, pi.re_code, pi.wh, pi.status, pi.require
                """), {"bid": batch_id}).fetchall()

                items = [dict(r._mapping) for r in rows]
                pending = [i for i in items if i["status"] != 2]  # status=2 = done
                free_scan_progress = {
                    "batch_id": batch_id,
                    "total_items": len(items),
                    "pending_count": len(pending),
                    "is_complete": len(pending) == 0,
                    "items": items
                }
            except Exception as fs_err:
                logger.warning(f"[FreeScan restore] batch {batch_id}: {fs_err}")
        # ────────────────────────────────────────────────────────────────────

        return {
            "success": True,
            "target": target,
            "actual": actual,
            "free_scan_progress": free_scan_progress
        }
    except Exception as e:
        logger.error(f"Failed to read recipe status from PLC: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/plant/{plant_id}/clear-recipe")
def clear_recipe_in_plc(plant_id: int = Path(..., title="Plant ID (1, 2, or 3)")):
    """
    Clear the recipe in the PLC by writing an empty array (zeros), and reset Batch ID.
    """
    from plc_service import write_full_recipe_to_plc
    success = write_full_recipe_to_plc(
        batch_id="-",
        sku_id="-",
        steps=[],
        plant_id=plant_id
    )

    if not success:
        raise HTTPException(status_code=500, detail=f"Failed to clear recipe in PLC DB15{plant_id}1")

    return {"status": "success", "message": f"Recipe memory cleared for Plant {plant_id}"}


@router.post("/plant/{plant_id}/reset-batch/{batch_id}")
def reset_batch_soft(
    plant_id: int = Path(..., title="Plant ID (1, 2, or 3)"),
    batch_id: str = Path(..., title="Batch ID to soft-reset"),
    db: Session = Depends(get_db)
):
    """
    Soft Reset for a batch:
      1. Clear DB15x1 (Recipe)        — PLC forgets the recipe
      2. Clear DB15x7 (Actuals)       — PLC forgets execution history (current_seq → 0)
      3. Delete production_step_logs  — UI stamp times cleared
      4. Reset batch status → Pending — Batch can be restarted from Check-for-Production
    Prebatch records (FH/SPP boxes) are intentionally preserved.
    """
    from plc_service import write_full_recipe_to_plc, clear_actuals_in_plc, get_db_number, plc
    from sqlalchemy import text as _text

    results = {}

    # ── 0. Clear DB15x0 (Step Command) ────────────────────────────────────────
    try:
        db_cmd_number = get_db_number('step_cmd', plant_id)
        zeros_cmd = b'\x00' * 88
        r0 = plc.db_write(db_cmd_number, 0, zeros_cmd)
        results["clear_step_cmd_db1510"] = "ok" if r0 else "failed"
        logger.info(f"[Reset] DB15{plant_id}0 clear: {results['clear_step_cmd_db1510']}")
    except Exception as cmd_err:
        results["clear_step_cmd_db1510"] = f"failed: {cmd_err}"
        logger.error(f"[Reset] Failed to clear DB15{plant_id}0: {cmd_err}")

    # ── 1. Clear DB15x1 (Recipe) ──────────────────────────────────────────────
    r1 = write_full_recipe_to_plc(batch_id="-", sku_id="-", steps=[], plant_id=plant_id)
    results["clear_recipe_db1511"] = "ok" if r1 else "failed"
    logger.info(f"[Reset] DB15{plant_id}1 clear: {results['clear_recipe_db1511']}")

    # ── 2. Clear DB15x7 (Actuals) ─────────────────────────────────────────────
    r2 = clear_actuals_in_plc(plant_id)
    results["clear_actuals_db1517"] = "ok" if r2 else "failed"
    logger.info(f"[Reset] DB15{plant_id}7 clear: {results['clear_actuals_db1517']}")

    # ── 3. Delete production_step_logs for this batch ─────────────────────────
    try:
        deleted = db.execute(
            _text("DELETE FROM production_step_logs WHERE batch_id = :bid"),
            {"bid": batch_id}
        )
        db.commit()
        results["clear_step_logs"] = f"ok ({deleted.rowcount} rows deleted)"
        logger.info(f"[Reset] Step logs cleared for {batch_id}: {deleted.rowcount} rows")
    except Exception as e:
        db.rollback()
        results["clear_step_logs"] = f"failed: {e}"
        logger.error(f"[Reset] Failed to clear step logs: {e}")

    # ── 4. Reset batch status → Pending ───────────────────────────────────────
    try:
        db.execute(
            _text("""
                UPDATE production_batches
                SET status = 'Pending', updated_at = NOW()
                WHERE batch_id = :bid
            """),
            {"bid": batch_id}
        )
        db.commit()
        results["reset_batch_status"] = "ok (→ Pending)"
        logger.info(f"[Reset] Batch {batch_id} status → Pending")
    except Exception as e:
        db.rollback()
        results["reset_batch_status"] = f"failed: {e}"
        logger.error(f"[Reset] Failed to reset batch status: {e}")

    # ── 5. Reset handshake worker in-memory state for this plant ──────────────
    try:
        from worker_handshake import _last_batch_id, _last_finished_step
        _last_batch_id[plant_id] = ""          # Force batch-change detection on next poll
        _last_finished_step[plant_id] = -1     # Reset step tracker so step 1 is not skipped
        results["reset_worker_state"] = "ok (tracker cleared)"
        logger.info(f"[Reset] Worker state cleared for Plant {plant_id} — _last_batch_id='', _last_finished_step=-1")
    except Exception as e:
        results["reset_worker_state"] = f"warning: {e}"
        logger.warning(f"[Reset] Could not reset worker state: {e}")

    all_ok = all(v.startswith("ok") for v in results.values())
    return {
        "status": "success" if all_ok else "partial",
        "batch_id": batch_id,
        "plant_id": plant_id,
        "results": results,
        "message": "Soft reset complete. PLC memory cleared, step logs deleted, batch → Pending. Prebatch records preserved."
        if all_ok else "Some steps failed — check results for details."
    }


@router.post("/plant/{plant_id}/force-next-step")
def force_next_step(
    plant_id: int = Path(..., title="Plant ID 1/2/3"),
    reason: str = "manual_bypass",
    db: Session = Depends(get_db)
):
    """
    [Emergency] Force advance to next PLC step — bypasses Free-Scan validation.
    Used when DB is down or operator needs to skip a stuck step.
    Writes DB15X7.SEQ+1 and pulses Cmd_NewStep.
    """
    import struct, time
    from plc_service import read_full_actuals, get_db_number, plc as plc_client

    try:
        actuals = read_full_actuals(plant_id)
        if not actuals:
            raise HTTPException(status_code=503, detail="Cannot read PLC actuals — PLC offline?")

        current_seq = actuals.get("current_seq", 0)
        batch_id    = actuals.get("batch_id", "-")
        next_seq    = current_seq + 1

        # Write SEQ+1 → DB15X7 offset +46 (Int, big-endian)
        db_actual = get_db_number("actual", plant_id)
        plc_client.db_write(db_actual, 46, bytearray(struct.pack(">h", next_seq)))

        # Pulse Cmd_NewStep → DB15X0 offset +86 (Bool bit)
        db_cmd = get_db_number("step_command", plant_id)
        plc_client.db_write(db_cmd, 86, bytearray([0x80]))
        time.sleep(0.15)
        plc_client.db_write(db_cmd, 86, bytearray([0x00]))

        logger.warning(
            f"[ForceNextStep] Plant={plant_id} batch={batch_id} "            f"SEQ {current_seq}→{next_seq} | reason={reason}"
        )

        # Log to DB (non-critical)
        try:
            from sqlalchemy import text as sa_text
            db.execute(sa_text("""
                INSERT INTO batch_event_logs (batch_id, plant_id, event_type, detail, created_at)
                VALUES (:bid, :pid, :etype, :detail, NOW())
            """), {
                "bid": batch_id, "pid": plant_id,
                "etype": "FORCE_NEXT_STEP",
                "detail": f"SEQ {current_seq}→{next_seq} | reason={reason}"
            })
            db.commit()
        except Exception:
            pass  # Table may not exist yet — non-critical

        return {
            "success": True,
            "plant_id": plant_id,
            "batch_id": batch_id,
            "prev_seq": current_seq,
            "next_seq": next_seq,
            "reason": reason,
            "message": f"Force advanced SEQ {current_seq} → {next_seq}"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[ForceNextStep] Plant={plant_id} error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# P2: LOCAL BATCH CACHE — Emergency fallback when DB is DOWN
# =============================================================================

@router.get("/batch-cache/list")
def list_batch_caches():
    """List all locally cached batches (emergency recovery reference)."""
    from batch_cache_service import list_cached_batches
    return {"cached_batches": list_cached_batches()}

@router.get("/batch-cache/{batch_id}")
def get_batch_cache(batch_id: str):
    """
    Retrieve locally cached recipe for a batch.
    Used as fallback when MySQL is unreachable.
    """
    from batch_cache_service import load_batch_cache
    data = load_batch_cache(batch_id)
    if not data:
        raise HTTPException(status_code=404, detail=f"No local cache for batch {batch_id}")
    return {"source": "local_cache", "data": data}

@router.get("/batch-cache/latest/auto")
def get_latest_batch_cache():
    """Get most recent cached batch — used after server crash when batch_id unknown."""
    from batch_cache_service import get_latest_cache
    data = get_latest_cache()
    if not data:
        raise HTTPException(status_code=404, detail="No local cache found")
    return {"source": "local_cache", "data": data}


# ─────────────────────────────────────────────────────────────────────────────
# Recipe Sequencer Endpoints (recipe_sequencer.py)
# ─────────────────────────────────────────────────────────────────────────────
from recipe_sequencer import build_execution_sequence, validate_step

# ─────────────────────────────────────────────────────────────────────────────
# Recipe Sequencer Endpoints (recipe_sequencer.py)
# ─────────────────────────────────────────────────────────────────────────────
from recipe_sequencer import build_execution_sequence, validate_step

def _sku_steps_to_dicts(sku_steps_orm):
    """Convert SkuStep ORM objects to plain dicts for recipe_sequencer."""
    return [
        {
            "phase_number":    s.phase_number,
            "phase_id":        s.phase_id,
            "sub_step":        s.sub_step,
            "master_step":     s.master_step,
            "plc_step_no":     s.plc_step_no,
            "phase_type_code": s.phase_type_code,
            "action_code":     s.action_code,
            "re_code":         s.re_code,
            "action_description": getattr(s, 'action_description', None),
            "require":         getattr(s, 'require', None),
            "uom":             getattr(s, 'uom', None),
            "step_time":       s.step_time,
            "temperature":     s.temperature,
            "temp_low":        getattr(s, 'temp_low', None),
            "temp_high":       getattr(s, 'temp_high', None),
            "agitator_rpm":    s.agitator_rpm,
            "high_shear_rpm":  s.high_shear_rpm,
        }
        for s in sku_steps_orm
    ]


@router.get("/recipe-sequence/{sku_id}")
def get_recipe_sequence(sku_id: str, db: Session = Depends(get_db)):
    """
    Preview PLC execution sequence for a SKU.
    Returns step groups in PLC order (2→4→6→...→28) regardless of DB entry order.
    Also auto-inserts gate steps (e.g. step 14) when triggered by A1020 phases.
    """
    sku_steps = db.query(models.SkuStep).filter(
        models.SkuStep.sku_id == sku_id
    ).order_by(models.SkuStep.phase_number, models.SkuStep.sub_step).all()

    if not sku_steps:
        raise HTTPException(status_code=404, detail=f"No steps for SKU '{sku_id}'")

    steps = _sku_steps_to_dicts(sku_steps)
    return build_execution_sequence(steps)


@router.get("/recipe-validate/{sku_id}")
def validate_recipe_steps(sku_id: str, db: Session = Depends(get_db)):
    """
    Validate DB plc_step_no against calculated FC_MapPhaseToStep values.
    Returns list of mismatches — กรณีคนกรอก plc_step_no ผิด.
    """
    sku_steps = db.query(models.SkuStep).filter(
        models.SkuStep.sku_id == sku_id
    ).order_by(models.SkuStep.phase_number, models.SkuStep.sub_step).all()

    if not sku_steps:
        raise HTTPException(status_code=404, detail=f"No steps for SKU '{sku_id}'")

    steps = _sku_steps_to_dicts(sku_steps)
    results = [validate_step(s) for s in steps]
    mismatches = [r for r in results if not r['ok']]
    return {
        "sku_id":        sku_id,
        "total_steps":   len(results),
        "mismatches":    len(mismatches),
        "all_ok":        len(mismatches) == 0,
        "details":       results,
    }

@router.post("/plant/{plant_id}/step-complete")
def api_set_step_complete(plant_id: int):
    """
    Triggered by the App to set DB15x3 Offset 0.0 (Step_complete) = True.
    Used for steps where App holds the logic (e.g. Scanning, QC Pass).
    """
    from plc_service import set_step_complete_in_plc
    success = set_step_complete_in_plc(plant_id)
    if success:
        return {"status": "success", "message": f"Step_complete set to True for Plant {plant_id}"}
    else:
        raise HTTPException(status_code=500, detail="Failed to write to PLC Handshake DB")
