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

    # 4. Convert ORM objects to dicts
    step_dicts = []
    for s in sku_steps:
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
            "agitator_rpm": s.agitator_rpm,
            "high_shear_rpm": s.high_shear_rpm,
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

    # Convert to UDT layout steps
    step_dicts = []
    for idx, s in enumerate(sorted_steps):
        phase_no_val = int(re.sub(r'^[a-zA-Z]+', '', str(s.phase_number or '0').strip()) or 0)
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
            "agitator_sp": float(s.agitator_rpm or 0.0),
            "highshear_sp": float(s.high_shear_rpm or 0.0),
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
    except Exception as e:
        logger.error(f"Failed to write recipe to real PLC: {e}")
        raise HTTPException(
            status_code=502,
            detail=f"Real hardware communication failed: snap7 error: {str(e)}"
        )

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
    In modern architecture, this often publishes to MQTT or writes via S7.
    """
    # 1. (Optional) Log to database for traceability
    logger.info(f"Received Step Command: {command.Step_ID} for Batch {command.Batch_ID}")

    # 2. (Implementation) Write to PLC or Publish to MQTT
    # payload = command.serialize()
    # mqtt_client.publish("MPL/PLC/DB100", payload)

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

from plc_service import read_recipe_from_plc

@router.get("/plant/{plant_id}/recipe-status")
def get_plant_recipe_status(plant_id: str):
    """
    Read the Recipe (Target) and Actual Results directly from the PLC via snap7 based on plant_id.
    """
    try:
        from plc_service import get_db_number
        recipe_db = get_db_number('full_recipe', int(plant_id))
        actual_db = get_db_number('actual', int(plant_id))
        
        target = read_recipe_from_plc(recipe_db)
        actual = read_recipe_from_plc(actual_db)
        
        return {
            "success": True,
            "target": target,
            "actual": actual
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
