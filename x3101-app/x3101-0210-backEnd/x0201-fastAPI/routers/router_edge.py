from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import Any
import logging

from database import get_db, get_local_db, _check_local_db

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/edge",
    tags=["Edge Local Buffer"]
)


@router.post("/start-batch/{batch_id}")
def sync_batch_to_edge(
    batch_id: str, 
    remote_db: Session = Depends(get_db), 
    local_db: Session = Depends(get_local_db)
):
    import models
    # Fetch Remote Batch Info
    batch = remote_db.query(models.ProductionBatch).filter(models.ProductionBatch.batch_id == batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found in cloud DB")
        
    plan = remote_db.query(models.ProductionPlan).filter(models.ProductionPlan.id == batch.plan_id).first()
    sku_code = plan.sku_id if plan else "UNKNOWN"
    sku_name = plan.sku_name if plan and plan.sku_name else None
    
    # If the production plan was missing the sku_name description, look it up from sku_masters!
    if not sku_name and sku_code != "UNKNOWN":
        sku_master = remote_db.query(models.Sku).filter(models.Sku.sku_id == sku_code).first()
        if sku_master:
            sku_name = sku_master.sku_name
    
    # Fetch Remote Steps
    remote_steps = remote_db.query(models.SkuStep).filter(models.SkuStep.sku_id == sku_code).all()
    
    try:
        # UPSERT active batch
        local_db.execute(text("""
            INSERT INTO local_production_queue (batch_id, plan_id, sku_code, sku_name, plant_id, target_total_weight, status, start_time)
            VALUES (:batch_id, :plan_id, :sku_code, :sku_name, :plant, :target_weight, 'RUNNING', NOW())
            ON DUPLICATE KEY UPDATE status='RUNNING', sku_code=:sku_code, plan_id=:plan_id, sku_name=:sku_name
        """), {
            "batch_id": batch.batch_id,
            "plan_id": plan.plan_id if plan else None,
            "sku_code": sku_code,
            "sku_name": sku_name,
            "plant": 1,
            "target_weight": batch.batch_size
        })

        # Clear existing cached steps for this SKU to prevent duplication
        local_db.execute(text("DELETE FROM local_sku_steps WHERE sku_code = :sku_code"), {"sku_code": sku_code})
        
        # Insert steps sequentially
        for step in remote_steps:
            local_db.execute(text("""
                INSERT INTO local_sku_steps 
                (sku_code, phase_no, phase_id, step_id, require_weight, require_temp, require_agitator_rpm, require_ph, require_brix, require_time_sec)
                VALUES (:sku, :phase, :phase_id, :step_id, :rw, :rt, :rar, :rph, :rb, :rtime)
            """), {
                "sku": sku_code,
                "phase": step.phase_number or 1,
                "phase_id": step.phase_id or "UNKNOWN",
                "step_id": step.sub_step,
                "rw": step.require or 0,
                "rt": step.temperature or 0,
                "rar": step.agitator_rpm or "0",
                "rph": step.ph_sp or "0",
                "rb": step.brix_sp or "0",
                "rtime": step.step_time or 0
            })
            
        local_db.commit()
    except Exception as e:
        local_db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
        
    # Mark batch as Active in Remote DB as well!
    try:
        batch.status = "RUNNING"
        remote_db.commit()
    except:
        remote_db.rollback()

    return {"status": "success", "message": f"Successfully pulled {batch_id} into Edge Buffer!"}


@router.get("/active-batch")
def get_active_batch():
    """Get active batch from local edge buffer.
    Fast-fails with 503 if local DB is not reachable (no 5s timeout).
    """
    if not _check_local_db():
        raise HTTPException(status_code=503, detail="Local edge DB is offline")
    try:
        from database import _get_local_session_maker
        session_maker = _get_local_session_maker()
        db = session_maker()
        try:
            result = db.execute(text("SELECT * FROM local_production_queue WHERE status = 'RUNNING' ORDER BY id DESC LIMIT 1")).fetchone()
            if not result:
                return None
            return dict(result._mapping)
        finally:
            db.close()
    except Exception as e:
        logger.warning("Edge active-batch query failed: %s", e)
        raise HTTPException(status_code=503, detail="Local edge DB query failed")

@router.get("/sku-steps/{sku_code}")
def get_local_sku_steps(sku_code: str):
    """Get SKU steps from local edge buffer.
    Fast-fails with 503 if local DB is not reachable.
    """
    if not _check_local_db():
        raise HTTPException(status_code=503, detail="Local edge DB is offline")
    try:
        from database import _get_local_session_maker
        session_maker = _get_local_session_maker()
        db = session_maker()
        try:
            rows = db.execute(text("SELECT * FROM local_sku_steps WHERE sku_code = :sku ORDER BY phase_no ASC, step_id ASC"), {"sku": sku_code}).fetchall()
            return [dict(row._mapping) for row in rows]
        finally:
            db.close()
    except Exception as e:
        logger.warning("Edge sku-steps query failed: %s", e)
        raise HTTPException(status_code=503, detail="Local edge DB query failed")

