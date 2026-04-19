"""
PLC Router — Recipe Data for S7-1200
=====================================
Endpoints to build and serve PLC recipe payloads for DB 1780.
"""

from fastapi import APIRouter, Depends, HTTPException
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
    # 1. Find the batch
    batch = db.query(models.ProductionBatch).filter(
        models.ProductionBatch.batch_id == batch_id
    ).first()
    if not batch:
        raise HTTPException(status_code=404, detail=f"Batch '{batch_id}' not found")

    # 2. Find the plan
    plan = db.query(models.ProductionPlan).filter(
        models.ProductionPlan.id == batch.plan_id
    ).first()
    if not plan:
        raise HTTPException(status_code=404, detail=f"Plan for batch '{batch_id}' not found")

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
def send_recipe_to_plc(batch_id: str, db: Session = Depends(get_db)):
    """
    (Future) Send recipe to PLC via snap7.
    Currently returns the recipe payload for verification.
    """
    payload = get_recipe_for_plc(batch_id, db)

    # TODO: snap7 integration
    # import snap7
    # plc = snap7.client.Client()
    # plc.connect('192.168.1.1', 0, 1)
    # data = serialize_to_bytes(payload)  # Convert to S7 byte array
    # plc.db_write(1780, 0, data)
    # plc.disconnect()

    payload["Header"]["RecipeReady"] = True
    return {
        "status": "prepared",
        "message": f"Recipe prepared for batch {batch_id} (snap7 not connected)",
        "recipe": payload,
    }


# =============================================================================
# DB100: STEP COMMAND (App ➔ PLC)
# =============================================================================

from plc_interface import DB100StepCommand, DB200Telemetry

@router.post("/step-command")
def send_step_command(command: DB100StepCommand, db: Session = Depends(get_db)):
    """
    Push a new step command/setpoint to the PLC (DB100).
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
_last_telemetry = DB200Telemetry()

@router.get("/telemetry", response_model=DB200Telemetry)
def get_plc_telemetry():
    """
    Get the latest telemetry data from the PLC (DB200).
    Values come from MQTT bridge or background S7 polling.
    """
    global _last_telemetry
    
    # In a real environment, this might query Redis or a live cache
    return _last_telemetry

@router.post("/telemetry/update")
def update_plc_telemetry(data: DB200Telemetry):
    """
    Endpoint for MQTT-bridge or worker to push latest PLC state (DB200).
    """
    global _last_telemetry
    _last_telemetry = data
    _last_telemetry.Last_Update = datetime.now()
    return {"status": "updated"}
