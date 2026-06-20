"""
Production Router
=================
Production plans, batches, and related endpoints.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, text
from typing import List, Optional
from datetime import datetime
import logging

import crud
import models
import schemas
from database import get_db

from pydantic import BaseModel
class RecheckBagRequest(BaseModel):
    box_id: str = ""  # Optional — use batch_id instead for batch-level recheck
    batch_id: str = ""  # Optional — used for batch-level recheck
    bag_barcode: str
    operator: str

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Production"])


# =============================================================================
# PRODUCTION PLAN ENDPOINTS
# =============================================================================

@router.get("/production-plans/")
def get_production_plans(skip: int = 0, limit: int = 1000, status: Optional[str] = None, db: Session = Depends(get_db)):
    """Get production plans with server-side pagination and status filter.
    status='active' excludes Cancelled and Done. status='all' shows everything.
    Returns {plans: [...], total: N}.
    """
    from sqlalchemy import text as sql_text, bindparam
    
    # Build WHERE clause based on status filter
    where_clause = ""
    params = {"limit": limit, "skip": skip}
    if status == "active":
        where_clause = "WHERE status NOT IN ('Cancelled', 'Done')"
    elif status and status not in ("all", ""):
        where_clause = "WHERE status = :status_val"
        params["status_val"] = status
    
    # Get total count
    total = db.execute(sql_text(f"SELECT COUNT(*) FROM production_plans {where_clause}"), params).scalar()
    
    # 1. Fetch plans
    plans = db.execute(sql_text(f"""
        SELECT id, plan_id, sku_id, sku_name, plant, total_volume, total_plan_volume,
               batch_size, num_batches, start_date, finish_date, status,
               flavour_house, spp, created_by, updated_by, created_at, updated_at
        FROM production_plans
        {where_clause}
        ORDER BY created_at DESC
        LIMIT :limit OFFSET :skip
    """), params).fetchall()
    
    plan_ids = [p.id for p in plans]
    
    # 2. Fetch batches for these plans (single query)
    batches_by_plan: dict = {}
    batches_with_logs = set()
    if plan_ids:
        # Fetch batches
        batches = db.execute(
            sql_text("""
                SELECT id, plan_id, batch_id, sku_id, plant, batch_size, status,
                       flavour_house, spp, batch_prepare, ready_to_product, production, done,
                       fh_boxed_at, spp_boxed_at, fh_delivered_at, fh_delivered_by,
                       spp_delivered_at, spp_delivered_by, created_at, updated_at
                FROM production_batches
                WHERE plan_id IN :plan_ids
            """).bindparams(bindparam("plan_ids", expanding=True)),
            {"plan_ids": plan_ids}
        ).fetchall()
        
        # Fetch batch IDs that actually have step execution logs
        log_rows = db.execute(
            sql_text("""
                SELECT DISTINCT l.batch_id 
                FROM production_step_logs l
                JOIN production_batches b ON l.batch_id = b.batch_id
                WHERE b.plan_id IN :plan_ids
            """).bindparams(bindparam("plan_ids", expanding=True)),
            {"plan_ids": plan_ids}
        ).fetchall()
        batches_with_logs = {r.batch_id for r in log_rows}
        
        for b in batches:
            pid = b.plan_id
            if pid not in batches_by_plan:
                batches_by_plan[pid] = []
            
            # Demote 'Done' status to Prepared or Created if there are no step logs
            status_val = b.status
            if status_val == "Done" and b.batch_id not in batches_with_logs:
                status_val = "Prepared" if bool(b.batch_prepare) else "Created"
                
            batches_by_plan[pid].append({
                "id": b.id, "plan_id": b.plan_id, "batch_id": b.batch_id,
                "sku_id": b.sku_id, "plant": b.plant, "batch_size": b.batch_size,
                "status": status_val, "flavour_house": bool(b.flavour_house),
                "spp": bool(b.spp), "batch_prepare": bool(b.batch_prepare),
                "ready_to_product": bool(b.ready_to_product),
                "production": bool(b.production), "done": bool(b.done),
                "fh_boxed_at": b.fh_boxed_at, "spp_boxed_at": b.spp_boxed_at,
                "fh_delivered_at": b.fh_delivered_at, "fh_delivered_by": b.fh_delivered_by,
                "spp_delivered_at": b.spp_delivered_at, "spp_delivered_by": b.spp_delivered_by,
                "created_at": b.created_at, "updated_at": b.updated_at,
            })
    
    # 2b. Fetch recheck/packing stats per batch from prebatch_recs, split by warehouse
    recheck_map = {}
    if plan_ids:
        # Overall recheck stats using plan_ids to reduce IN clause size
        rc_rows = db.execute(sql_text("""
            SELECT 
                q.batch_id AS bid,
                COUNT(r.id) AS total,
                SUM(CASE WHEN r.recheck_status = 1 THEN 1 ELSE 0 END) AS recheck_ok,
                SUM(CASE WHEN r.recheck_status = 2 THEN 1 ELSE 0 END) AS recheck_err,
                SUM(CASE WHEN r.packing_status = 1 THEN 1 ELSE 0 END) AS packed
            FROM prebatch_recs r
            JOIN prebatch_reqs q ON r.req_id = q.id
            JOIN production_batches b ON q.batch_id = b.batch_id
            WHERE b.plan_id IN :plan_ids
            GROUP BY q.batch_id
        """).bindparams(bindparam("plan_ids", expanding=True)), {"plan_ids": plan_ids}).fetchall()
        for r in rc_rows:
            recheck_map[r.bid] = {
                'total': int(r.total), 'recheck_ok': int(r.recheck_ok),
                'recheck_err': int(r.recheck_err), 'packed': int(r.packed),
                'fh_packed': 0, 'spp_packed': 0, 'fh_total': 0, 'spp_total': 0,
            }
        
        # Per-warehouse packed counts
        wh_rows = db.execute(sql_text("""
            SELECT 
                q.batch_id AS bid,
                COALESCE(q.wh, 'Mix') AS wh,
                COUNT(r.id) AS total,
                SUM(CASE WHEN r.packing_status = 1 THEN 1 ELSE 0 END) AS packed
            FROM prebatch_recs r
            JOIN prebatch_reqs q ON r.req_id = q.id
            JOIN production_batches b ON q.batch_id = b.batch_id
            WHERE b.plan_id IN :plan_ids
            GROUP BY q.batch_id, wh
        """).bindparams(bindparam("plan_ids", expanding=True)), {"plan_ids": plan_ids}).fetchall()
        for r in wh_rows:
            if r.bid in recheck_map:
                w = (r.wh or '').upper()
                if w == 'FH':
                    recheck_map[r.bid]['fh_packed'] = int(r.packed)
                    recheck_map[r.bid]['fh_total'] = int(r.total)
                elif w == 'SPP':
                    recheck_map[r.bid]['spp_packed'] = int(r.packed)
                    recheck_map[r.bid]['spp_total'] = int(r.total)
    
    # Inject recheck stats into batch dicts
    empty_rc = {'total': 0, 'recheck_ok': 0, 'recheck_err': 0, 'packed': 0,
                'fh_packed': 0, 'spp_packed': 0, 'fh_total': 0, 'spp_total': 0}
    for blist in batches_by_plan.values():
        for bd in blist:
            rc = recheck_map.get(bd["batch_id"], empty_rc)
            bd["recheck_total"] = rc['total']
            bd["recheck_ok"] = rc['recheck_ok']
            bd["recheck_err"] = rc['recheck_err']
            bd["packed"] = rc['packed']
            bd["fh_packed"] = rc['fh_packed']
            bd["spp_packed"] = rc['spp_packed']
            bd["fh_total"] = rc['fh_total']
            bd["spp_total"] = rc['spp_total']
    
    # 3. Fetch aggregated ingredients per plan (single query)
    ingredients_by_plan: dict = {}
    plan_id_strs = [p.plan_id for p in plans if p.plan_id]
    if plan_id_strs:
        ing_rows = db.execute(sql_text("""
            SELECT 
                r.plan_id,
                r.re_code,
                r.ingredient_name,
                i.warehouse AS wh,
                i.mat_sap_code,
                r.required_volume AS vol_per_batch,
                SUM(r.required_volume) AS total_vol
            FROM prebatch_reqs r
            LEFT JOIN ingredients i ON i.re_code = r.re_code
            WHERE r.plan_id IN :plan_ids
            GROUP BY r.plan_id, r.re_code, r.ingredient_name, i.warehouse, i.mat_sap_code, r.required_volume
            ORDER BY i.warehouse, r.re_code
        """).bindparams(bindparam("plan_ids", expanding=True)),
        {"plan_ids": plan_id_strs}).fetchall()
        
        for r in ing_rows:
            pid = r.plan_id  # string plan_id
            if pid not in ingredients_by_plan:
                ingredients_by_plan[pid] = []
            ingredients_by_plan[pid].append({
                "re_code": r.re_code,
                "mat_sap_code": r.mat_sap_code or "",
                "name": r.ingredient_name or r.re_code,
                "wh": r.wh or "-",
                "vol_per_batch": float(r.vol_per_batch or 0),
                "total_vol": float(r.total_vol or 0),
            })
    
    # 4. Fetch phase info from sku_steps
    sku_ids = list(set(p.sku_id for p in plans if p.sku_id))
    phase_map: dict = {}  # sku_id -> re_code -> phases
    if sku_ids:
        phase_rows = db.execute(sql_text("""
            SELECT sku_id, re_code, GROUP_CONCAT(DISTINCT phase_number ORDER BY phase_number) AS phases
            FROM sku_steps
            WHERE sku_id IN :sku_ids
            GROUP BY sku_id, re_code
        """).bindparams(bindparam("sku_ids", expanding=True)),
        {"sku_ids": sku_ids}).fetchall()
        for pr in phase_rows:
            if pr.sku_id not in phase_map:
                phase_map[pr.sku_id] = {}
            phase_map[pr.sku_id][pr.re_code] = pr.phases or ""
    
    # 5. Assemble result
    result = []
    for p in plans:
        # Add phases to ingredients
        plan_ingredients = ingredients_by_plan.get(p.plan_id, [])
        sku_phases = phase_map.get(p.sku_id, {})
        for ing in plan_ingredients:
            ing["phases"] = sku_phases.get(ing["re_code"], "")
        
        result.append({
            "id": p.id, "plan_id": p.plan_id, "sku_id": p.sku_id,
            "sku_name": p.sku_name, "plant": p.plant,
            "total_volume": p.total_volume, "total_plan_volume": p.total_plan_volume,
            "batch_size": p.batch_size, "num_batches": p.num_batches,
            "start_date": p.start_date, "finish_date": p.finish_date,
            "status": p.status, "flavour_house": bool(p.flavour_house),
            "spp": bool(p.spp), "created_by": p.created_by,
            "updated_by": p.updated_by, "created_at": p.created_at,
            "updated_at": p.updated_at,
            "batches": batches_by_plan.get(p.id, []),
            "ingredients": plan_ingredients,
        })
    
    return {"plans": result, "total": total}


@router.get("/production-plans/{plan_id}", response_model=schemas.ProductionPlan)
def get_production_plan(plan_id: int, db: Session = Depends(get_db)):
    """Get a specific production plan by database ID."""
    db_plan = crud.get_production_plan(db, plan_id=plan_id)
    if not db_plan:
        raise HTTPException(status_code=404, detail="Production plan not found")
    return db_plan

@router.post("/production-plans/", response_model=schemas.ProductionPlan)
def create_production_plan(plan: schemas.ProductionPlanCreate, db: Session = Depends(get_db)):
    """Create a new production plan and its batches."""
    return crud.create_production_plan(db=db, plan_data=plan)

@router.put("/production-plans/{plan_id}", response_model=schemas.ProductionPlan)
def update_production_plan(plan_id: int, plan: schemas.ProductionPlanCreate, db: Session = Depends(get_db)):
    """Update a production plan."""
    db_plan = crud.update_production_plan(db, plan_id=plan_id, plan_update=plan)
    if not db_plan:
        raise HTTPException(status_code=404, detail="Production plan not found")
    return db_plan

@router.delete("/production-plans/{plan_id}")
def cancel_production_plan(plan_id: int, cancel_data: schemas.ProductionPlanCancel, db: Session = Depends(get_db)):
    """Cancel a production plan and its batches."""
    db_plan = crud.cancel_production_plan(
        db, 
        plan_id=plan_id, 
        comment=cancel_data.comment, 
        changed_by=cancel_data.changed_by
    )
    if not db_plan:
        raise HTTPException(status_code=404, detail="Production plan not found")
    return {"status": "success", "message": "Plan and batches cancelled"}


# =============================================================================
# PRODUCTION BATCH ENDPOINTS
# =============================================================================

@router.get("/production-batches/summary")
def get_production_batches_summary(db: Session = Depends(get_db)):
    """Fast summary of all batches (id, batch_id, status only) — no JOINs.
    Used by the dashboard for counts and activity feeds."""
    rows = db.query(
        models.ProductionBatch.id,
        models.ProductionBatch.batch_id,
        models.ProductionBatch.sku_id,
        models.ProductionBatch.status,
        models.ProductionBatch.created_at,
        models.ProductionBatch.updated_at,
    ).order_by(models.ProductionBatch.created_at.desc()).limit(1000).all()
    return [
        {"id": r.id, "batch_id": r.batch_id, "sku_id": r.sku_id,
         "status": r.status, "created_at": r.created_at, "updated_at": r.updated_at}
        for r in rows
    ]

@router.get("/production-batches/done-all")
def get_all_done_batches(db: Session = Depends(get_db)):
    """Return ALL Done batches with completed_at + last_operator from step logs.
    Used by Production Report to ensure Done batches are never hidden by pagination limit.
    """
    from sqlalchemy import text as _sql
    rows = db.execute(_sql("""
        SELECT
            pb.id, pb.batch_id, pb.sku_id, pb.plant, pb.batch_size,
            pb.status, pb.done, pb.created_at, pb.updated_at,
            pp.plan_id, pp.sku_name,
            MAX(psl.completed_at)  AS completed_at,
            SUBSTRING_INDEX(
                GROUP_CONCAT(psl.operator ORDER BY psl.completed_at DESC SEPARATOR ','),
                ',', 1
            )                      AS last_operator
        FROM production_batches pb
        LEFT JOIN production_plans pp  ON pp.id = pb.plan_id
        LEFT JOIN production_step_logs psl ON psl.batch_id = pb.batch_id
        WHERE pb.status = 'Done'
        GROUP BY pb.id, pb.batch_id, pb.sku_id, pb.plant, pb.batch_size,
                 pb.status, pb.done, pb.created_at, pb.updated_at,
                 pp.plan_id, pp.sku_name
        ORDER BY MAX(psl.completed_at) DESC
    """)).fetchall()
    return [
        {
            "id": r.id, "batch_id": r.batch_id, "sku_id": r.sku_id,
            "sku_name": r.sku_name or r.sku_id,
            "plant": r.plant, "batch_size": float(r.batch_size or 0),
            "status": r.status, "done": bool(r.done),
            "plan_id": r.plan_id,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "updated_at": r.updated_at.isoformat() if r.updated_at else None,
            "completed_at": r.completed_at.isoformat() if r.completed_at else None,
            "last_operator": r.last_operator or "—",
        }
        for r in rows
    ]

@router.get("/production-batches/", response_model=List[schemas.ProductionBatch])
def get_production_batches(skip: int = 0, limit: int = 1000, db: Session = Depends(get_db)):
    """Get all production batches."""
    return crud.get_production_batches(db, skip=skip, limit=limit)

# NOTE: This must come BEFORE /production-batches/{batch_id} to avoid route conflict
@router.get("/production-batches/done-all")
def get_done_batches(db: Session = Depends(get_db)):
    """Get all completed batches (bypasses limit to ensure all reports can be viewed)."""
    with track_performance("GET /production-batches/done-all") as tracker:
        results = db.query(models.ProductionBatch).filter(
            models.ProductionBatch.status == 'Done'
        ).order_by(models.ProductionBatch.updated_at.desc()).all()
        tracker.record_count = len(results)
        return results

# NOTE: This must come BEFORE /production-batches/{batch_id} to avoid route conflict
@router.get("/production-batches/box-contents/{batch_id_str}")
def get_box_contents(batch_id_str: str, db: Session = Depends(get_db)):
    """Get box contents for a batch, grouped by WH → re_code → packages.
    Uses prebatch_items directly — each item row IS a package.
    """
    from sqlalchemy import text as sql_text3

    # Get all items from prebatch_items (the packing list — each row = one package)
    items = db.execute(sql_text3("""
        SELECT i.id, i.re_code, i.ingredient_name, i.wh,
               i.required_volume, i.net_volume,
               i.status, i.packing_status, i.batch_record_id,
               i.package_no, i.total_packages
        FROM prebatch_items i
        WHERE i.batch_id = :bid
        ORDER BY i.wh, i.re_code, i.package_no
    """), {"bid": batch_id_str}).fetchall()

    # Build hierarchical structure: WH → re_code → packages (items)
    wh_map: dict = {}
    total_box_weight = 0.0
    for item in items:
        wh = item.wh or "Mix"
        if wh not in wh_map:
            wh_map[wh] = {"wh": wh, "re_codes": {}, "total_weight": 0.0}
        wh_node = wh_map[wh]

        re = item.re_code or "?"
        if re not in wh_node["re_codes"]:
            wh_node["re_codes"][re] = {
                "re_code": re,
                "ingredient_name": item.ingredient_name or re,
                "required_volume": float(item.required_volume or 0),
                "status": item.status or 0,
                "packing_status": item.packing_status or 0,
                "packages": [],
                "total_weight": 0.0,
            }
        re_node = wh_node["re_codes"][re]

        nv = float(item.net_volume or 0)
        re_node["packages"].append({
            "id": item.id,
            "batch_record_id": item.batch_record_id or "",
            "package_no": item.package_no or 1,
            "total_packages": item.total_packages or 1,
            "net_volume": nv,
            "required_volume": float(item.required_volume or 0),
            "packing_status": item.packing_status or 0,
            "recheck_status": 0,
        })
        re_node["total_weight"] += nv
        # Also accumulate required_volume (sum across duplicate re_codes)
        re_node["required_volume"] = float(item.required_volume or 0)
        wh_node["total_weight"] += nv
        total_box_weight += nv

    # Convert dicts to lists
    wh_groups = []
    for wh_node in wh_map.values():
        wh_node["re_codes"] = sorted(wh_node["re_codes"].values(), key=lambda x: x["re_code"])
        wh_groups.append(wh_node)

    return {
        "batch_id": batch_id_str,
        "wh_groups": wh_groups,
        "total_box_weight": round(total_box_weight, 4),
    }


@router.get("/production-batches/ready-to-deliver")
def get_ready_to_deliver(show_all: bool = False, db: Session = Depends(get_db)):
    """Get batches that have at least one boxed warehouse but are not yet delivered.
    If show_all=True, returns ALL batches with full status pipeline."""
    if show_all:
        batches = db.query(models.ProductionBatch).all()
    else:
        batches = db.query(models.ProductionBatch).filter(
            (models.ProductionBatch.fh_boxed_at.isnot(None)) | (models.ProductionBatch.spp_boxed_at.isnot(None)),
        ).all()

    # Get recheck/packing summary from prebatch_recs per batch
    recheck_map = {}
    if show_all:
        from sqlalchemy import text as sql_text2
        # Overall recheck stats
        rc_rows = db.execute(sql_text2("""
            SELECT
                SUBSTRING_INDEX(r.batch_record_id, '-', 4) AS bid,
                COUNT(*) AS total,
                SUM(CASE WHEN r.recheck_status = 1 THEN 1 ELSE 0 END) AS recheck_ok,
                SUM(CASE WHEN r.recheck_status = 2 THEN 1 ELSE 0 END) AS recheck_err,
                SUM(CASE WHEN r.packing_status = 1 THEN 1 ELSE 0 END) AS packed
            FROM prebatch_recs r
            GROUP BY bid
        """)).fetchall()
        for r in rc_rows:
            recheck_map[r.bid] = {
                'total': int(r.total), 'recheck_ok': int(r.recheck_ok),
                'recheck_err': int(r.recheck_err), 'packed': int(r.packed),
                'fh_packed': 0, 'spp_packed': 0, 'fh_total': 0, 'spp_total': 0,
            }
        # Per-warehouse packed counts
        wh_rows = db.execute(sql_text2("""
            SELECT
                SUBSTRING_INDEX(r.batch_record_id, '-', 4) AS bid,
                COALESCE(q.wh, 'Mix') AS wh,
                COUNT(*) AS total,
                SUM(CASE WHEN r.packing_status = 1 THEN 1 ELSE 0 END) AS packed
            FROM prebatch_recs r
            LEFT JOIN prebatch_reqs q ON q.id = r.req_id
            GROUP BY bid, wh
        """)).fetchall()
        for r in wh_rows:
            if r.bid in recheck_map:
                w = (r.wh or '').upper()
                if w == 'FH':
                    recheck_map[r.bid]['fh_packed'] = int(r.packed)
                    recheck_map[r.bid]['fh_total'] = int(r.total)
                elif w == 'SPP':
                    recheck_map[r.bid]['spp_packed'] = int(r.packed)
                    recheck_map[r.bid]['spp_total'] = int(r.total)

    empty_rc = {'total': 0, 'recheck_ok': 0, 'recheck_err': 0, 'packed': 0,
                'fh_packed': 0, 'spp_packed': 0, 'fh_total': 0, 'spp_total': 0}
    result = []
    for b in batches:
        rc = recheck_map.get(b.batch_id, empty_rc)
        result.append({
            "id": b.id,
            "batch_id": b.batch_id,
            "sku_id": b.sku_id,
            "plant": b.plant,
            "batch_size": b.batch_size,
            "production": bool(b.production),
            "flavour_house": bool(b.flavour_house),
            "spp": bool(b.spp),
            "batch_prepare": bool(b.batch_prepare),
            "ready_to_product": bool(b.ready_to_product),
            "done": bool(b.done),
            "recheck_total": rc['total'],
            "recheck_ok": rc['recheck_ok'],
            "recheck_err": rc['recheck_err'],
            "packed": rc['packed'],
            "fh_packed": rc['fh_packed'],
            "spp_packed": rc['spp_packed'],
            "fh_total": rc['fh_total'],
            "spp_total": rc['spp_total'],
            "fh_boxed_at": b.fh_boxed_at.isoformat() if b.fh_boxed_at else None,
            "spp_boxed_at": b.spp_boxed_at.isoformat() if b.spp_boxed_at else None,
            "fh_delivered_at": b.fh_delivered_at.isoformat() if b.fh_delivered_at else None,
            "fh_delivered_by": b.fh_delivered_by,
            "spp_delivered_at": b.spp_delivered_at.isoformat() if b.spp_delivered_at else None,
            "spp_delivered_by": b.spp_delivered_by,
        })
    return result

# =============================================================================
# RE-CHECK / VERIFICATION LOGIC
# =============================================================================

@router.get("/production-batches/awaiting-recheck")
def get_batches_awaiting_recheck(db: Session = Depends(get_db)):
    """Return batches that are boxed but not yet released to production."""
    rows = db.query(models.ProductionBatch, models.ProductionPlan).join(
        models.ProductionPlan, models.ProductionBatch.plan_id == models.ProductionPlan.id
    ).filter(
        (models.ProductionBatch.fh_boxed_at.isnot(None)) | (models.ProductionBatch.spp_boxed_at.isnot(None)),
        models.ProductionBatch.ready_to_product == False
    ).all()

    return [{
        "batch_id": b.batch_id,
        "plan_id": p.plan_id if p else "-",
        "sku_id": b.sku_id,
        "sku_name": p.sku_name if p else "-",
        "plant": b.plant or "-",
        "batch_size": b.batch_size or 0,
        "fh_boxed": b.fh_boxed_at is not None,
        "spp_boxed": b.spp_boxed_at is not None,
    } for b, p in rows]

@router.get("/prebatch-recs/recheck-batch/{batch_id}")
def get_recheck_batch_details(batch_id: str, db: Session = Depends(get_db)):
    """
    Get ALL required items for a batch for re-check verification.
    Source of truth: prebatch_reqs (requirements).
    Cross-referenced with: prebatch_recs (actual packed packages).
    """
    # 1. Find the production batch
    batch = db.query(models.ProductionBatch).filter(
        models.ProductionBatch.batch_id == batch_id
    ).first()
    if not batch:
        raise HTTPException(status_code=404, detail=f"Batch '{batch_id}' not found")

    plan = db.query(models.ProductionPlan).filter(
        models.ProductionPlan.id == batch.plan_id
    ).first()
    sku_id = plan.sku_id if plan else None

    # 2. Get all requirements for this batch (source of truth)
    reqs = db.query(models.PreBatchReq).filter(
        models.PreBatchReq.batch_id == batch_id
    ).all()

    # 3. Get all packed records for this batch
    recs = db.query(models.PreBatchRec).filter(
        models.PreBatchRec.batch_record_id.like(f"{batch_id}%")
    ).all()

    # 4. Build checklist from requirements, enriched with packed record data
    checklist = []
    all_box_ids = set()

    for req in reqs:
        # MIX ingredients are dispensed during production, not pre-packed
        wh_clean = (req.wh or "FH").upper()
        if wh_clean in ("MIX", "MIXING"):
            continue

        # Find matching packed records for this requirement
        matching_recs = [r for r in recs if r.req_id == req.id]
        packed_count = len(matching_recs)
        packed_volume = sum(r.net_volume or 0 for r in matching_recs)
        total_packages = matching_recs[0].total_packages if matching_recs else 0

        # Determine recheck status from recs
        if packed_count > 0:
            all_checked = all(r.recheck_status == 1 for r in matching_recs)
            any_error = any(r.recheck_status == 2 for r in matching_recs)
            recheck_status = 1 if all_checked else (2 if any_error else 0)
        else:
            # Fallback: check prebatch_items table when no packed recs exist
            linked_item = db.query(models.PreBatchItem).filter(
                models.PreBatchItem.batch_id == batch_id,
                models.PreBatchItem.re_code == req.re_code,
            ).first()
            recheck_status = (linked_item.recheck_status or 0) if linked_item else 0

        # Batch record IDs for this requirement (for scanning verification)
        rec_ids = [r.batch_record_id for r in matching_recs]

        checklist.append({
            "req_id": req.id,
            "re_code": req.re_code,
            "ingredient_name": req.ingredient_name,
            "wh": req.wh or "FH",
            "required_volume": req.required_volume or 0,
            "packed_volume": round(packed_volume, 3),
            "packed_count": packed_count,
            "total_packages": total_packages,
            "recheck_status": recheck_status,
            "batch_record_ids": rec_ids,
            "status": req.status,  # 0=Pending, 1=In-Progress, 2=Completed
        })

    # 5. Summary
    total = len(checklist)
    checked = sum(1 for c in checklist if c["recheck_status"] == 1)
    errors = sum(1 for c in checklist if c["recheck_status"] == 2)
    pending = total - checked - errors

    return {
        "batch_id": batch_id,
        "plan_id": plan.plan_id if plan else None,
        "sku_id": sku_id,
        "sku_name": plan.sku_name if plan else "Unknown",
        "plant": batch.plant,
        "box_ids": sorted(all_box_ids),
        "fh_boxed_at": batch.fh_boxed_at.isoformat() if batch.fh_boxed_at else None,
        "spp_boxed_at": batch.spp_boxed_at.isoformat() if batch.spp_boxed_at else None,
        "checklist": checklist,
        "summary": {
            "total": total,
            "checked": checked,
            "errors": errors,
            "pending": pending,
            "all_ok": checked == total and total > 0,
        }
    }

@router.get("/prebatch-recs/recheck-box/{box_id}")
def get_recheck_box_details(box_id: str, db: Session = Depends(get_db)):
    """
    Get all bags for a box/batch with target volumes and tolerances for re-check.
    """
    # 1. Find all bags actually weighed for this box
    records = db.query(models.PreBatchRec).filter(
        models.PreBatchRec.batch_record_id.like(f"{box_id}%")
    ).all()

    if not records:
        # Maybe box_id is a partial or plan_id, try finding by plan_id
        records = db.query(models.PreBatchRec).filter(
            models.PreBatchRec.plan_id == box_id
        ).all()

    if not records:
        raise HTTPException(status_code=404, detail="No packing bags found for this Box ID")

    # Get Plan and SKU to find tolerances
    plan_id = records[0].plan_id
    plan = db.query(models.ProductionPlan).filter(models.ProductionPlan.plan_id == plan_id).first()
    sku_id = plan.sku_id if plan else None

    # ── Batch-fetch all related data upfront (avoids N+1 queries) ──
    # Pre-fetch all requirements for these records
    req_ids = list(set(r.req_id for r in records if r.req_id))
    req_map = {}
    if req_ids:
        reqs = db.query(models.PreBatchReq).filter(models.PreBatchReq.id.in_(req_ids)).all()
        req_map = {req.id: req for req in reqs}

    # Pre-fetch all SKU step tolerances for this SKU's re_codes
    step_map = {}
    if sku_id:
        re_codes = list(set(r.re_code for r in records if r.re_code))
        if re_codes:
            steps = db.query(models.SkuStep).filter(
                models.SkuStep.sku_id == sku_id,
                models.SkuStep.re_code.in_(re_codes)
            ).all()
            for step in steps:
                step_map[step.re_code] = step

    result_bags = []
    for r in records:
        # Get target from requirement (O(1) lookup)
        req = req_map.get(r.req_id)
        target_vol = req.required_volume if req else r.total_volume
        
        # Get tolerance from SKU steps (O(1) lookup)
        tolerance = 0.05 # Default 50g if not found
        step = step_map.get(r.re_code)
        if step:
            # Use high_tol if available, else 1% of target
            tolerance = step.high_tol if step.high_tol and step.high_tol > 0 else (target_vol * 0.01)

        result_bags.append({
            "id": r.id,
            "batch_record_id": r.batch_record_id,
            "re_code": r.re_code,
            "package_no": r.package_no,
            "total_packages": r.total_packages,
            "net_volume": r.net_volume,
            "target_volume": target_vol,
            "tolerance": tolerance,
            "status": r.recheck_status,
            "recheck_at": r.recheck_at,
            "recheck_by": r.recheck_by,
            "is_valid": abs((r.net_volume or 0) - (target_vol or 0)) <= tolerance
        })

    return {
        "box_id": box_id,
        "plan_id": plan_id,
        "sku_id": sku_id,
        "sku_name": plan.sku_name if plan else "Unknown",
        "total_bags": len(records),
        "bags": result_bags
    }

@router.get("/production-batches/{batch_id}", response_model=schemas.ProductionBatch)

def get_production_batch(batch_id: int, db: Session = Depends(get_db)):
    """Get a specific production batch by database ID."""
    db_batch = crud.get_production_batch(db, batch_id=batch_id)
    if not db_batch:
        raise HTTPException(status_code=404, detail="Production batch not found")
    return db_batch

@router.put("/production-batches/{batch_id}", response_model=schemas.ProductionBatch)
def update_production_batch(batch_id: int, batch: schemas.ProductionBatchUpdate, db: Session = Depends(get_db)):
    """Update a production batch."""
    db_batch = crud.update_production_batch(db, batch_id=batch_id, batch_update=batch)
    if not db_batch:
        raise HTTPException(status_code=404, detail="Production batch not found")
    return db_batch

@router.patch("/production-batches/{batch_id}/status", response_model=schemas.ProductionBatch)
def update_production_batch_status(batch_id: int, status: str, db: Session = Depends(get_db)):
    """Quickly update batch status."""
    db_batch = crud.update_production_batch_status(db, batch_id=batch_id, status=status)
    if not db_batch:
        raise HTTPException(status_code=404, detail="Production batch not found")
    return db_batch


class HoldBatchRequest(BaseModel):
    held_by: Optional[str] = "operator"
    reason: Optional[str] = None


@router.patch("/production-batches/hold/{batch_id_str}")
def hold_batch(batch_id_str: str, data: HoldBatchRequest, db: Session = Depends(get_db)):
    """Put a batch on Hold.
    Saves the previous status in a remark so Unhold can restore it.
    FIFO: the next In-Progress batch in the same plan remains active.
    """
    batch = db.query(models.ProductionBatch).filter(
        models.ProductionBatch.batch_id == batch_id_str
    ).first()
    if not batch:
        raise HTTPException(status_code=404, detail=f"Batch '{batch_id_str}' not found")
    if batch.status == "Hold":
        raise HTTPException(status_code=400, detail="Batch is already on Hold")
    if batch.status in ("Done", "Cancelled"):
        raise HTTPException(status_code=400, detail=f"Cannot hold a batch with status '{batch.status}'")

    prev_status = batch.status
    batch.status = "Hold"
    batch.updated_at = datetime.now()

    # Log into plan history for audit trail
    plan = db.query(models.ProductionPlan).filter(
        models.ProductionPlan.id == batch.plan_id
    ).first()
    if plan:
        history = models.ProductionPlanHistory(
            plan_db_id=plan.id,
            action="hold_batch",
            old_status=prev_status,
            new_status="Hold",
            remarks=f"Batch {batch_id_str} held. Prev={prev_status}. Reason: {data.reason or '-'}. By: {data.held_by}",
            changed_by=data.held_by or "operator",
        )
        db.add(history)

    db.commit()
    db.refresh(batch)
    return {
        "batch_id": batch.batch_id,
        "status": batch.status,
        "previous_status": prev_status,
        "held_by": data.held_by,
        "message": f"Batch '{batch_id_str}' is now on Hold. Previous status: {prev_status}."
    }


@router.patch("/production-batches/unhold/{batch_id_str}")
def unhold_batch(batch_id_str: str, data: HoldBatchRequest, db: Session = Depends(get_db)):
    """Release a batch from Hold — restores it to 'In-Progress' (FIFO queue).
    The batch re-enters the queue and the operator can work on it next.
    """
    batch = db.query(models.ProductionBatch).filter(
        models.ProductionBatch.batch_id == batch_id_str
    ).first()
    if not batch:
        raise HTTPException(status_code=404, detail=f"Batch '{batch_id_str}' not found")
    if batch.status != "Hold":
        raise HTTPException(status_code=400, detail=f"Batch is not on Hold (current: {batch.status})")

    # Always restore to In-Progress so it re-enters the FIFO queue
    batch.status = "In-Progress"
    batch.updated_at = datetime.now()

    plan = db.query(models.ProductionPlan).filter(
        models.ProductionPlan.id == batch.plan_id
    ).first()
    if plan:
        history = models.ProductionPlanHistory(
            plan_db_id=plan.id,
            action="unhold_batch",
            old_status="Hold",
            new_status="In-Progress",
            remarks=f"Batch {batch_id_str} released from Hold. By: {data.held_by}",
            changed_by=data.held_by or "operator",
        )
        db.add(history)

    db.commit()
    db.refresh(batch)
    return {
        "batch_id": batch.batch_id,
        "status": batch.status,
        "message": f"Batch '{batch_id_str}' released from Hold → In-Progress."
    }

@router.get("/production-batches/by-batch-id/{batch_id_str}")
def get_production_batch_by_id_str(batch_id_str: str, db: Session = Depends(get_db)):
    """Get a specific production batch by its string ID, enriched with sku_name from the plan."""
    db_batch = db.query(models.ProductionBatch).filter(models.ProductionBatch.batch_id == batch_id_str).first()
    if not db_batch:
        raise HTTPException(status_code=404, detail="Production batch not found")
    # Enrich with sku_name from the parent plan
    plan = db.query(models.ProductionPlan).filter(models.ProductionPlan.id == db_batch.plan_id).first()
    result = schemas.ProductionBatch.model_validate(db_batch).model_dump()
    result["sku_name"] = plan.sku_name if plan else "-"
    return result

@router.post("/production-batches/by-batch-id/{batch_id_str}/ensure-reqs")
def ensure_batch_reqs(batch_id_str: str, db: Session = Depends(get_db)):
    """Ensure PreBatchReq records exist for a batch (creates from SKU recipe if missing)."""
    from crud.crud_prebatch import ensure_prebatch_reqs_for_batch
    success = ensure_prebatch_reqs_for_batch(db, batch_id_str)
    if not success:
        raise HTTPException(status_code=400, detail="Could not create requirements")
    reqs = db.query(models.PreBatchReq).filter(models.PreBatchReq.batch_id == batch_id_str).all()
    return [{"id": r.id, "re_code": r.re_code, "batch_id": r.batch_id, "required_volume": r.required_volume, "wh": r.wh} for r in reqs]


# =============================================================================
# PREBATCH RECORD ENDPOINTS
# =============================================================================

@router.get("/prebatch-recs/summary/{batch_id}")
@router.get("/prebatch_recs/summary/{batch_id}")
def get_prebatch_records_summary(batch_id: str, db: Session = Depends(get_db)):
    """
    Returns a summary of prebatch records grouped by ingredient.
    Matches records by either batch_record_id prefix or plan_id.
    """
    # Try searching by full batch ID prefix first
    records = db.query(models.PreBatchRec).filter(
        models.PreBatchRec.batch_record_id.like(f"{batch_id}%")
    ).all()
    
    # If no records found, try searching by plan_id if the batch_id looks like a Plan ID
    # or find records where plan_id matches the prefix of the batch_id
    if not records:
        # Example batch_id: plan-Line-3-2026-02-07-003-003
        # Extract plan part: plan-Line-3-2026-02-07-003
        plan_part = "-".join(batch_id.split("-")[:-1]) if "-" in batch_id else batch_id
        records = db.query(models.PreBatchRec).filter(
            models.PreBatchRec.plan_id == plan_part
        ).all()
    
    summary = {}
    for r in records:
        if r.re_code not in summary:
            # Try to find ingredient name
            ing = db.query(models.Ingredient).filter(models.Ingredient.re_code == r.re_code).first()
            summary[r.re_code] = {
                "id": r.req_id,
                "re_code": r.re_code,
                "ingredient_name": ing.name if ing else r.re_code,
                "required_volume": r.total_volume or 0,
                "net_volume": 0,
                "package_count": 0,
                "total_packages": r.total_packages or 0,
                "wh": r.req.wh if r.req else "-",
                "status": 1
            }
        
        summary[r.re_code]["net_volume"] += r.net_volume or 0
        summary[r.re_code]["package_count"] += 1
        
        if r.package_no >= (r.total_packages or 0) and r.total_packages:
            summary[r.re_code]["status"] = 2

    return list(summary.values())

@router.get("/prebatch-recs/", response_model=List[schemas.PreBatchRec])
def get_prebatch_recs(skip: int = 0, limit: int = 1000, wh: Optional[str] = None, db: Session = Depends(get_db)):
    """Get all prebatch records."""
    return crud.get_prebatch_recs(db, skip=skip, limit=limit, wh=wh)


@router.get("/prebatch-recs/by-batch/{batch_id}", response_model=List[schemas.PreBatchRec])
def get_prebatch_recs_by_batch(batch_id: str, db: Session = Depends(get_db)):
    """Get prebatch records filtered by batch ID."""
    return crud.get_prebatch_recs_by_batch(db, batch_id=batch_id)

@router.get("/prebatch-recs/by-req-ids")
def get_prebatch_recs_by_req_ids(req_ids: str, db: Session = Depends(get_db)):
    """Get prebatch recs for multiple req_ids (comma-separated). Returns {req_id: [recs]}."""
    ids = [int(x) for x in req_ids.split(",") if x.strip().isdigit()]
    if not ids:
        return {}
    recs = db.query(models.PreBatchRec).filter(models.PreBatchRec.req_id.in_(ids)).all()
    result: dict = {}
    for rec in recs:
        rid = rec.req_id
        if rid not in result:
            result[rid] = []
        result[rid].append({
            "id": rec.id,
            "batch_record_id": rec.batch_record_id,
            "package_no": rec.package_no,
            "total_packages": rec.total_packages,
            "net_volume": rec.net_volume,
            "packing_status": rec.packing_status,
        })
    return result

@router.get("/prebatch-recs/by-plan/{plan_id}", response_model=List[schemas.PreBatchRec])
def get_prebatch_recs_by_plan(plan_id: str, db: Session = Depends(get_db)):
    """Get prebatch records filtered by production plan ID."""
    return crud.get_prebatch_recs_by_plan(db, plan_id=plan_id)

@router.post("/prebatch-recs/", response_model=schemas.PreBatchRec)
def create_prebatch_rec(record: schemas.PreBatchRecCreate, db: Session = Depends(get_db)):
    """Create a new prebatch record (transaction)."""
    return crud.create_prebatch_rec(db=db, record=record)

@router.delete("/prebatch-recs/{record_id}")
def delete_prebatch_rec(record_id: int, db: Session = Depends(get_db)):
    """Delete a prebatch record and revert inventory."""
    success = crud.delete_prebatch_rec(db, record_id=record_id)
    if not success:
        raise HTTPException(status_code=404, detail="Record not found")
    return {"status": "success"}


@router.delete("/prebatch-recs/clear-batch/{batch_id_str}")
def clear_batch_records(batch_id_str: str, db: Session = Depends(get_db)):
    """Clear ALL prebatch records for a batch and restore inventory.
    This resets the batch so it can be re-weighed from scratch."""
    from sqlalchemy import text as sql_text_clear

    # 1. Find all PreBatchRec records for this batch
    recs = db.query(models.PreBatchRec).filter(
        models.PreBatchRec.batch_record_id.like(f"{batch_id_str}%")
    ).all()

    if not recs:
        raise HTTPException(status_code=404, detail=f"No records found for batch {batch_id_str}")

    deleted_count = 0
    for rec in recs:
        # Restore inventory (same logic as single delete)
        if rec.intake_lot_id and rec.net_volume:
            inv = db.query(models.IngredientIntakeList).filter(
                models.IngredientIntakeList.intake_lot_id == rec.intake_lot_id,
                models.IngredientIntakeList.re_code == rec.re_code,
            ).first()
            if inv:
                inv.remain_vol = (inv.remain_vol or 0) + (rec.net_volume or 0)
        db.delete(rec)
        deleted_count += 1

    # 2. Reset PreBatchItems for this batch
    items = db.query(models.PreBatchItem).filter(
        models.PreBatchItem.batch_id == batch_id_str
    ).all()
    for item in items:
        # Clear origins
        db.query(models.PreBatchItemFrom).filter(
            models.PreBatchItemFrom.prebatch_item_id == item.id
        ).delete()
        # Reset item fields
        item.batch_record_id = None
        item.net_volume = None
        item.package_no = 1
        item.total_packages = 1
        item.intake_lot_id = None
        item.mat_sap_code = None
        item.prebatch_id = None
        item.recode_batch_id = None
        item.total_volume = None
        item.total_request_volume = None
        item.weighed_at = None
        item.recheck_status = 0
        item.packing_status = 0
        item.status = 0  # Back to Wait

    # 3. Reset PreBatchReq status
    reqs = db.query(models.PreBatchReq).filter(
        models.PreBatchReq.batch_id == batch_id_str
    ).all()
    for req in reqs:
        req.status = 0

    # 4. Reset batch prepare flag
    batch = db.query(models.ProductionBatch).filter(
        models.ProductionBatch.batch_id == batch_id_str
    ).first()
    if batch:
        batch.batch_prepare = False
        if batch.status == "Prepared":
            batch.status = "In-Progress"

    db.commit()
    return {
        "status": "success",
        "deleted_records": deleted_count,
        "message": f"Cleared {deleted_count} records for batch {batch_id_str}"
    }


class PackingStatusUpdate(BaseModel):
    packing_status: int  # 0=Unpacked, 1=Packed
    packed_by: Optional[str] = None


@router.patch("/prebatch-recs/{record_id}/packing-status")
def update_packing_status(record_id: int, data: PackingStatusUpdate, db: Session = Depends(get_db)):
    """Update the packing status of a prebatch record (0=Unpacked, 1=Packed)."""
    rec = db.query(models.PreBatchRec).filter(models.PreBatchRec.id == record_id).first()
    if not rec:
        raise HTTPException(status_code=404, detail="Record not found")

    rec.packing_status = data.packing_status
    if data.packing_status == 1:
        rec.packed_at = datetime.now()
        rec.packed_by = data.packed_by or "operator"
    else:
        rec.packed_at = None
        rec.packed_by = None

    db.commit()
    db.refresh(rec)
    return {
        "id": rec.id,
        "packing_status": rec.packing_status,
        "packed_at": rec.packed_at,
        "packed_by": rec.packed_by,
    }

@router.patch("/prebatch-recs/{record_id}/recheck-status")
def update_recheck_status(record_id: int, status: int, db: Session = Depends(get_db)):
    """Quickly update recheck_status for a record."""
    rec = db.query(models.PreBatchRec).filter(models.PreBatchRec.id == record_id).first()
    if not rec:
        raise HTTPException(status_code=404, detail="Record not found")
    rec.recheck_status = status
    rec.recheck_at = datetime.now() if status != 0 else None
    db.commit()
    return {"id": rec.id, "recheck_status": rec.recheck_status}

@router.patch("/prebatch-items/{item_id}/recheck-status")
def update_item_recheck_status(item_id: int, status: int, db: Session = Depends(get_db)):
    """Quickly update recheck_status for a prebatch item."""
    item = db.query(models.PreBatchItem).filter(models.PreBatchItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    item.recheck_status = status
    item.recheck_at = datetime.now() if status != 0 else None
    db.commit()
    return {"id": item.id, "recheck_status": item.recheck_status}

# =============================================================================
# PREBATCH ITEMS (NEW UNIFIED ENDPOINTS)
# =============================================================================

@router.get("/prebatch-items/summary-by-plan/{plan_id}")
def get_prebatch_items_summary(plan_id: str, db: Session = Depends(get_db)):
    """Ingredient summary across all batches — single GROUP BY query, no N+1."""
    from sqlalchemy import func as sqfunc
    rows = db.query(
        models.PreBatchItem.re_code,
        models.PreBatchItem.ingredient_name,
        models.PreBatchItem.wh,
        sqfunc.sum(models.PreBatchItem.required_volume).label("total_required"),
        sqfunc.sum(models.PreBatchItem.net_volume).label("total_packaged"),
        sqfunc.count(models.PreBatchItem.id).label("batch_count"),
        sqfunc.min(models.PreBatchItem.required_volume).label("per_batch_min"),
        sqfunc.sum(sqfunc.IF(models.PreBatchItem.status == 2, 1, 0)).label("completed_batches"),
    ).filter(
        models.PreBatchItem.plan_id == plan_id
    ).group_by(
        models.PreBatchItem.re_code,
        models.PreBatchItem.ingredient_name,
        models.PreBatchItem.wh,
    ).all()

    result = []
    for r in rows:
        total_req = round(float(r.total_required or 0), 4)
        total_pkg = round(float(r.total_packaged or 0), 4)
        batch_count = int(r.batch_count or 0)
        completed = int(r.completed_batches or 0)
        
        if completed >= batch_count and batch_count > 0:
            status = 2
        elif completed > 0:
            status = 1
        else:
            status = 0

        result.append({
            "re_code": r.re_code,
            "ingredient_name": r.ingredient_name,
            "total_required": total_req,
            "total_packaged": total_pkg,
            "batch_count": batch_count,
            "per_batch": float(r.per_batch_min or 0),
            "wh": r.wh or "-",
            "status": status,
            "completed_batches": completed,
        })
    return result


@router.get("/prebatch-items/batches-by-ingredient/{plan_id}/{re_code:path}")
def get_items_for_ingredient(plan_id: str, re_code: str, db: Session = Depends(get_db)):
    """Per-batch detail for an ingredient — single query, no N+1."""
    from urllib.parse import unquote
    re_code = unquote(re_code)
    
    items = db.query(models.PreBatchItem).filter(
        models.PreBatchItem.plan_id == plan_id,
        models.PreBatchItem.re_code == re_code
    ).order_by(models.PreBatchItem.batch_id).all()
    
    return [{
        "batch_id": item.batch_id,
        "required_volume": item.required_volume or 0,
        "actual_volume": round(float(item.net_volume or 0), 4),
        "net_volume": item.net_volume,
        "package_no": item.package_no or 1,
        "total_packages": item.total_packages or 1,
        "status": item.status,
        "req_id": item.id,  # item.id replaces old req.id
    } for item in items]


@router.get("/prebatch-items/by-batch/{batch_id}")
def get_items_by_batch(batch_id: str, db: Session = Depends(get_db)):
    """Get all items for a batch — single query."""
    items = db.query(models.PreBatchItem).filter(
        models.PreBatchItem.batch_id == batch_id
    ).all()
    return [{
        "id": item.id,
        "batch_db_id": item.batch_db_id,
        "plan_id": item.plan_id,
        "batch_id": item.batch_id,
        "re_code": item.re_code,
        "ingredient_name": item.ingredient_name,
        "required_volume": item.required_volume,
        "total_packaged": round(float(item.net_volume or 0), 4),
        "wh": item.wh,
        "status": item.status,
        "packing_status": item.packing_status or 0,
        "batch_record_id": item.batch_record_id,
        "recheck_status": item.recheck_status or 0,
        "recheck_at": item.recheck_at,
        "recheck_by": item.recheck_by,
    } for item in items]


@router.get("/prebatch-items/by-plan/{plan_id}")
def get_items_by_plan(plan_id: str, wh: Optional[str] = None, include_unpacked: bool = False, db: Session = Depends(get_db)):
    """Get all items for a plan, optionally filtered by warehouse. Only weighed items unless include_unpacked is True."""
    from sqlalchemy.orm import selectinload
    query = db.query(models.PreBatchItem).options(
        selectinload(models.PreBatchItem.origins)
    ).filter(
        models.PreBatchItem.plan_id == plan_id
    )

    if not include_unpacked:
        query = query.filter(models.PreBatchItem.net_volume.isnot(None))
    if wh and wh not in ("All", "All Warehouse"):
        query = query.filter(models.PreBatchItem.wh == wh)
    items = query.order_by(models.PreBatchItem.batch_id, models.PreBatchItem.re_code).all()
    return [schemas.PreBatchItem.model_validate(item) for item in items]


@router.put("/prebatch-items/{item_id}/status")
def update_item_status(item_id: int, status: int, db: Session = Depends(get_db)):
    """Update item status: 0=Wait, 1=Batch, 2=Done."""
    item = db.query(models.PreBatchItem).filter(models.PreBatchItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    item.status = status
    db.commit()
    return {"id": item.id, "status": item.status}


@router.put("/prebatch-items/{item_id}/pack")
def pack_item(item_id: int, data: schemas.PreBatchItemPack, db: Session = Depends(get_db)):
    """Pack (weigh) an item — creates a PreBatchRec for each package and accumulates net_volume."""
    item = db.query(models.PreBatchItem).filter(models.PreBatchItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    # --- GUARD 1: Duplicate batch_record_id check ---
    if data.batch_record_id:
        existing_rec = db.query(models.PreBatchRec).filter(
            models.PreBatchRec.batch_record_id == data.batch_record_id
        ).first()
        if existing_rec:
            raise HTTPException(
                status_code=409,
                detail=f"Duplicate: record '{data.batch_record_id}' already exists (package #{existing_rec.package_no})"
            )

    # --- GUARD 2: Over-pack protection ---
    required = item.required_volume or 0
    current_packed = float(item.net_volume or 0)
    new_weight = float(data.net_volume or 0)
    if required > 0 and (current_packed + new_weight) > required * 2:
        raise HTTPException(
            status_code=400,
            detail=f"Over-pack rejected: current {current_packed:.4f} + new {new_weight:.4f} = {current_packed + new_weight:.4f} kg exceeds 2× required {required:.4f} kg"
        )

    # Update item metadata (keep latest batch_record_id / package info)
    item.batch_record_id = data.batch_record_id
    item.package_no = data.package_no
    item.total_packages = data.total_packages
    item.intake_lot_id = data.intake_lot_id
    item.mat_sap_code = data.mat_sap_code
    item.recode_batch_id = data.recode_batch_id
    
    if data.new_required_volume is not None:
        item.required_volume = data.new_required_volume
        
    # ACCUMULATE net_volume — add this package's weight
    item.net_volume = (item.net_volume or 0) + (data.net_volume or 0)
    item.total_volume = item.required_volume
    item.total_request_volume = item.required_volume
    item.weighed_at = datetime.now()
    
    # Auto-format prebatch_id
    if item.recode_batch_id and item.re_code and item.batch_id:
        item.prebatch_id = f"{item.batch_id}{item.re_code}{item.recode_batch_id}"

    # Create a PreBatchRec child record for this individual package
    # (so frontend can display each package separately)
    req = db.query(models.PreBatchReq).filter(
        models.PreBatchReq.batch_id == item.batch_id,
        models.PreBatchReq.re_code == item.re_code,
    ).first()
    
    db_rec = models.PreBatchRec(
        req_id=req.id if req else None,
        batch_record_id=data.batch_record_id,
        plan_id=item.plan_id,
        re_code=item.re_code,
        mat_sap_code=data.mat_sap_code,
        package_no=data.package_no,
        total_packages=data.total_packages,
        net_volume=data.net_volume,
        total_volume=item.required_volume,
        total_request_volume=item.required_volume,
        intake_lot_id=data.intake_lot_id,
        prebatch_id=item.prebatch_id,
        recode_batch_id=data.recode_batch_id,
        recheck_status=0,
        packing_status=0,
    )
    db.add(db_rec)
    db.flush()

    # Also update PreBatchReq status if it exists
    if req:
        actual_count = db.query(models.PreBatchRec).filter(
            models.PreBatchRec.req_id == req.id,
            models.PreBatchRec.net_volume.isnot(None),
        ).count()
        if actual_count >= data.total_packages:
            req.status = 2  # Completed — ALL packages packed
        elif req.status == 0:
            req.status = 1  # In-Progress

    # Mark PreBatchItem status based on actual package count
    actual_item_pkgs = db.query(models.PreBatchRec).filter(
        models.PreBatchRec.plan_id == item.plan_id,
        models.PreBatchRec.re_code == item.re_code,
        models.PreBatchRec.prebatch_id == item.prebatch_id,
        models.PreBatchRec.net_volume.isnot(None),
    ).count()
    if actual_item_pkgs >= data.total_packages:
        item.status = 2  # Completed
    elif item.status == 0:
        item.status = 1  # In-Progress

    # Add origins (lot traceability) — linked to PreBatchItem
    if data.origins:
        for origin in data.origins:
            db.add(models.PreBatchItemFrom(
                prebatch_item_id=item.id,
                intake_lot_id=origin.intake_lot_id,
                mat_sap_code=origin.mat_sap_code,
                take_volume=origin.take_volume,
            ))
            # Deduct inventory
            inv = db.query(models.IngredientIntakeList).filter(
                models.IngredientIntakeList.intake_lot_id == origin.intake_lot_id,
                models.IngredientIntakeList.re_code == item.re_code,
            ).first()
            if inv:
                inv.remain_vol = (inv.remain_vol or 0) - origin.take_volume
    elif data.intake_lot_id:
        inv = db.query(models.IngredientIntakeList).filter(
            models.IngredientIntakeList.intake_lot_id == data.intake_lot_id,
            models.IngredientIntakeList.re_code == item.re_code,
        ).first()
        if inv:
            inv.remain_vol = (inv.remain_vol or 0) - (data.net_volume or 0)

    # Auto-finalize batch when all items done
    batch = db.query(models.ProductionBatch).filter(models.ProductionBatch.id == item.batch_db_id).first()
    if batch:
        all_items = db.query(models.PreBatchItem).filter(models.PreBatchItem.batch_db_id == batch.id).all()
        if all(i.status == 2 for i in all_items):
            batch.batch_prepare = True
            if batch.status in ("Created", "In-Progress"):
                batch.status = "Prepared"

    db.commit()
    db.refresh(item)
    return schemas.PreBatchItem.model_validate(item)


@router.delete("/prebatch-items/{item_id}/unpack")
def unpack_item(item_id: int, db: Session = Depends(get_db)):
    """Unpack (revert) a weighed item — clears packing fields and restores inventory."""
    item = db.query(models.PreBatchItem).filter(models.PreBatchItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    
    # Restore inventory from origins
    origins = db.query(models.PreBatchItemFrom).filter(
        models.PreBatchItemFrom.prebatch_item_id == item_id
    ).all()
    if origins:
        for origin in origins:
            inv = db.query(models.IngredientIntakeList).filter(
                models.IngredientIntakeList.intake_lot_id == origin.intake_lot_id,
                models.IngredientIntakeList.re_code == item.re_code,
            ).first()
            if inv:
                inv.remain_vol = (inv.remain_vol or 0) + origin.take_volume
            db.delete(origin)
    elif item.intake_lot_id and item.net_volume:
        inv = db.query(models.IngredientIntakeList).filter(
            models.IngredientIntakeList.intake_lot_id == item.intake_lot_id,
            models.IngredientIntakeList.re_code == item.re_code,
        ).first()
        if inv:
            inv.remain_vol = (inv.remain_vol or 0) + item.net_volume

    # Clear packing fields
    item.batch_record_id = None
    item.net_volume = None
    item.package_no = 1
    item.total_packages = 1
    item.intake_lot_id = None
    item.mat_sap_code = None
    item.prebatch_id = None
    item.recode_batch_id = None
    item.total_volume = None
    item.total_request_volume = None
    item.weighed_at = None
    item.recheck_status = 0
    item.recheck_at = None
    item.recheck_by = None
    item.packing_status = 0
    item.packed_at = None
    item.packed_by = None
    item.status = 1  # Back to in-progress

    db.commit()
    return {"status": "success", "message": "Item unpacked and inventory restored"}


@router.patch("/prebatch-items/{item_id}/packing-status")
def update_item_packing_status(item_id: int, data: PackingStatusUpdate, db: Session = Depends(get_db)):
    """Update packing status of a prebatch item."""
    item = db.query(models.PreBatchItem).filter(models.PreBatchItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    item.packing_status = data.packing_status
    if data.packing_status == 1:
        item.packed_at = datetime.now()
        item.packed_by = data.packed_by or "operator"
    else:
        item.packed_at = None
        item.packed_by = None
    db.commit()
    return {"id": item.id, "packing_status": item.packing_status}

# =============================================================================
# PACKING & DELIVERY ENDPOINTS
# =============================================================================

@router.patch("/production-batches/by-batch-id/{batch_id_str}/box-close")
def close_box(batch_id_str: str, data: schemas.BoxCloseRequest, db: Session = Depends(get_db)):
    """Mark a warehouse box as closed (Boxed) for a batch."""
    batch = db.query(models.ProductionBatch).filter(
        models.ProductionBatch.batch_id == batch_id_str
    ).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")

    wh = data.wh.upper()
    now = datetime.now()
    if wh == "FH":
        batch.fh_boxed_at = now
    elif wh == "SPP":
        batch.spp_boxed_at = now
    else:
        raise HTTPException(status_code=400, detail=f"Invalid warehouse: {wh}. Must be FH or SPP.")

    db.commit()
    db.refresh(batch)
    return {
        "status": "success",
        "batch_id": batch.batch_id,
        "wh": wh,
        "boxed_at": now.isoformat(),
        "fh_boxed_at": batch.fh_boxed_at.isoformat() if batch.fh_boxed_at else None,
        "spp_boxed_at": batch.spp_boxed_at.isoformat() if batch.spp_boxed_at else None,
    }


@router.patch("/production-batches/by-batch-id/{batch_id_str}/box-cancel")
def cancel_box(batch_id_str: str, data: schemas.BoxCancelRequest, db: Session = Depends(get_db)):
    """Cancel (revert) a closed packing box. Clears boxed_at and resets packing_status on items."""
    batch = db.query(models.ProductionBatch).filter(
        models.ProductionBatch.batch_id == batch_id_str
    ).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")

    wh = data.wh.upper()
    if wh == "FH":
        if not batch.fh_boxed_at:
            raise HTTPException(status_code=400, detail="FH box is not closed, nothing to cancel.")
        if batch.fh_delivered_at:
            raise HTTPException(status_code=400, detail="FH box already delivered. Cannot cancel after delivery.")
        batch.fh_boxed_at = None
    elif wh == "SPP":
        if not batch.spp_boxed_at:
            raise HTTPException(status_code=400, detail="SPP box is not closed, nothing to cancel.")
        if batch.spp_delivered_at:
            raise HTTPException(status_code=400, detail="SPP box already delivered. Cannot cancel after delivery.")
        batch.spp_boxed_at = None
    else:
        raise HTTPException(status_code=400, detail=f"Invalid warehouse: {wh}. Must be FH or SPP.")

    # Reset packing_status on prebatch_recs for this batch + WH
    from sqlalchemy import text as sql_cancel
    db.execute(sql_cancel("""
        UPDATE prebatch_recs r
        JOIN prebatch_reqs q ON q.id = r.req_id
        SET r.packing_status = 0, r.packed_at = NULL, r.packed_by = NULL
        WHERE q.batch_id = :bid AND q.wh = :wh AND r.packing_status = 1
    """), {"bid": batch_id_str, "wh": wh})

    # Reset packing_status on prebatch_items for this batch + WH
    db.execute(sql_cancel("""
        UPDATE prebatch_items
        SET packing_status = 0, packed_at = NULL, packed_by = NULL
        WHERE batch_id = :bid AND wh = :wh AND packing_status = 1
    """), {"bid": batch_id_str, "wh": wh})

    db.commit()
    db.refresh(batch)

    logger.info(
        "Box cancelled: batch=%s wh=%s reason='%s' by=%s",
        batch_id_str, wh, data.reason, data.cancelled_by or "operator"
    )

    return {
        "status": "success",
        "batch_id": batch.batch_id,
        "wh": wh,
        "reason": data.reason,
        "cancelled_by": data.cancelled_by or "operator",
        "fh_boxed_at": batch.fh_boxed_at.isoformat() if batch.fh_boxed_at else None,
        "spp_boxed_at": batch.spp_boxed_at.isoformat() if batch.spp_boxed_at else None,
    }


@router.patch("/production-batches/by-batch-id/{batch_id_str}/deliver")
def deliver_batch(batch_id_str: str, data: schemas.DeliveryRequest, db: Session = Depends(get_db)):
    """Mark a batch warehouse as delivered. FH→SPP or SPP→Production Hall."""
    batch = db.query(models.ProductionBatch).filter(
        models.ProductionBatch.batch_id == batch_id_str
    ).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")

    wh = data.wh.upper()
    now = datetime.now()
    operator = data.delivered_by or "operator"
    if wh == "FH":
        batch.fh_delivered_at = now
        batch.fh_delivered_by = operator
    elif wh == "SPP":
        batch.spp_delivered_at = now
        batch.spp_delivered_by = operator
    else:
        raise HTTPException(status_code=400, detail=f"Invalid warehouse: {wh}. Must be FH or SPP.")

    db.commit()
    db.refresh(batch)
    return {
        "status": "success",
        "batch_id": batch.batch_id,
        "wh": wh,
        "delivered_at": now.isoformat(),
        "delivered_by": operator,
    }


@router.patch("/production-batches/by-batch-id/{batch_id_str}/cancel-deliver")
def cancel_deliver_batch(batch_id_str: str, data: schemas.DeliveryRequest, db: Session = Depends(get_db)):
    """Undo a delivery — clear fh_delivered_at / spp_delivered_at."""
    batch = db.query(models.ProductionBatch).filter(
        models.ProductionBatch.batch_id == batch_id_str
    ).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")

    wh = data.wh.upper()
    if wh == "FH":
        batch.fh_delivered_at = None
        batch.fh_delivered_by = None
    elif wh == "SPP":
        batch.spp_delivered_at = None
        batch.spp_delivered_by = None
    else:
        raise HTTPException(status_code=400, detail=f"Invalid warehouse: {wh}. Must be FH or SPP.")

    db.commit()
    db.refresh(batch)
    logger.info("Delivery cancelled: batch=%s wh=%s by=%s", batch_id_str, wh, data.delivered_by or "operator")
    return {
        "status": "success",
        "batch_id": batch.batch_id,
        "wh": wh,
        "message": f"{wh} delivery undone",
    }



# =============================================================================
# DASHBOARD & ANALYTICS
# =============================================================================

@router.get("/production-stats/summary")
def get_production_summary_stats(db: Session = Depends(get_db)):
    """Get high-level production summary stats for dashboard."""
    total_plans = db.query(models.ProductionPlan).count()
    active_plans = db.query(models.ProductionPlan).filter(models.ProductionPlan.status == "In-Progress").count()
    completed_plans = db.query(models.ProductionPlan).filter(models.ProductionPlan.status == "Completed").count()
    
    total_batches = db.query(models.ProductionBatch).count()
    pending_batches = db.query(models.ProductionBatch).filter(models.ProductionBatch.status == "Created").count()
    done_batches = db.query(models.ProductionBatch).filter(models.ProductionBatch.status == "Done").count()
    in_progress_batches = db.query(models.ProductionBatch).filter(models.ProductionBatch.status == "In-Progress").count()
    prepared_batches = db.query(models.ProductionBatch).filter(models.ProductionBatch.status == "Prepared").count()
    cancelled_batches = db.query(models.ProductionBatch).filter(models.ProductionBatch.status == "Cancelled").count()
    
    # Simple count of records today
    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    records_today = db.query(models.PreBatchRec).filter(models.PreBatchRec.created_at >= today_start).count()
    
    return {
        "plans": {
            "total": total_plans,
            "active": active_plans,
            "completed": completed_plans
        },
        "batches": {
            "total": total_batches,
            "done": done_batches,
            "in_progress": in_progress_batches,
            "prepared": prepared_batches,
            "pending": pending_batches,
            "cancelled": cancelled_batches
        },
        "records_today": records_today,
        "timestamp": datetime.now()
    }

@router.post("/prebatch-recs/reset-batch/{batch_id}")
def reset_batch_recheck(batch_id: str, db: Session = Depends(get_db)):
    """Reset the recheck status for all prebatch_recs and prebatch_items for a batch."""
    
    # 1. Update prebatch_recs
    db.query(models.PreBatchRec).filter(
        models.PreBatchRec.batch_record_id.like(f"{batch_id}%")
    ).update({
        "recheck_status": 0,
        "recheck_at": None,
        "recheck_by": None
    }, synchronize_session=False)

    # 2. Update prebatch_items
    db.query(models.PreBatchItem).filter(
        models.PreBatchItem.batch_id == batch_id
    ).update({
        "recheck_status": 0,
        "recheck_at": None,
        "recheck_by": None
    }, synchronize_session=False)

    db.commit()
    return {"status": "OK", "message": f"Reset recheck status for batch {batch_id}"}

@router.post("/prebatch-recs/recheck-bag")
def verify_bag_scan(data: RecheckBagRequest, db: Session = Depends(get_db)):
    """
    Verify a single bag scan against a box or batch.
    Supports both box-level (box_id) and batch-level (batch_id) recheck.
    """
    ref_id = data.batch_id or data.box_id
    if not ref_id:
        raise HTTPException(status_code=400, detail="Either box_id or batch_id must be provided")

    # 1. Find the bag in prebatch_recs first
    bag = db.query(models.PreBatchRec).filter(models.PreBatchRec.batch_record_id == data.bag_barcode).first()

    # Also try to find in prebatch_items (SPP items may only exist here)
    item = None
    if not bag:
        item = db.query(models.PreBatchItem).filter(
            models.PreBatchItem.batch_id == ref_id,
            models.PreBatchItem.batch_record_id == data.bag_barcode
        ).first()
        # Fallback: match by re_code
        if not item:
            item = db.query(models.PreBatchItem).filter(
                models.PreBatchItem.batch_id == ref_id,
                models.PreBatchItem.re_code == data.bag_barcode
            ).first()

    if not bag and not item:
        raise HTTPException(status_code=404, detail=f"Bag barcode '{data.bag_barcode}' not found")

    # 2. Verify it belongs to the batch/box
    if bag:
        if data.batch_id:
            if not bag.batch_record_id.startswith(data.batch_id):
                raise HTTPException(status_code=400, detail=f"Bag does not belong to batch {data.batch_id}")
        elif data.box_id:
            if not bag.batch_record_id.startswith(data.box_id) and bag.plan_id != data.box_id:
                raise HTTPException(status_code=400, detail="Bag does not belong to this Box")

    # 3. Get target and tolerance
    if bag:
        req = db.query(models.PreBatchReq).filter(models.PreBatchReq.id == bag.req_id).first()
        target_vol = req.required_volume if req else bag.total_volume
        re_code = bag.re_code
        plan_id = bag.plan_id
    else:
        target_vol = item.required_volume or item.net_volume or 0
        re_code = item.re_code
        plan_id = item.plan_id

    plan = db.query(models.ProductionPlan).filter(models.ProductionPlan.plan_id == plan_id).first()
    tolerance = 0.05
    if plan:
        step = db.query(models.SkuStep).filter(
            models.SkuStep.sku_id == plan.sku_id,
            models.SkuStep.re_code == re_code
        ).first()
        if step:
            tolerance = step.high_tol if step.high_tol > 0 else (target_vol * 0.01)

    # 4. Perform check
    actual_vol = (bag.net_volume if bag else item.net_volume) or 0
    is_ok = abs(actual_vol - (target_vol or 0)) <= tolerance

    # 5. Update Status
    if bag:
        bag.recheck_status = 1 if is_ok else 2
        bag.recheck_at = datetime.now()
        bag.recheck_by = data.operator
        
        # Sync recheck status to the corresponding prebatch_item.
        # If all recs for this re_code in the batch are verified, mark item as verified too.
        req = db.query(models.PreBatchReq).filter(models.PreBatchReq.id == bag.req_id).first()
        if req:
            all_recs = db.query(models.PreBatchRec).filter(
                models.PreBatchRec.req_id == req.id
            ).all()
            all_verified = all(r.recheck_status == 1 for r in all_recs)
            any_failed = any(r.recheck_status == 2 for r in all_recs)
            synced_status = 2 if any_failed else (1 if all_verified else 0)
            
            linked_item = db.query(models.PreBatchItem).filter(
                models.PreBatchItem.batch_id == req.batch_id,
                models.PreBatchItem.re_code == req.re_code,
            ).first()
            if linked_item:
                linked_item.recheck_status = synced_status
                if synced_status > 0:
                    linked_item.recheck_at = datetime.now()
                    linked_item.recheck_by = data.operator

    if item:
        item.recheck_status = 1 if is_ok else 2
        item.recheck_at = datetime.now()
        item.recheck_by = data.operator
    db.commit()

    return {
        "status": "OK" if is_ok else "ERROR",
        "message": "Verify Success" if is_ok else "Weight Mismatch",
        "bag": {
            "re_code": bag.re_code,
            "batch_record_id": bag.batch_record_id,
            "actual": bag.net_volume,
            "target": target_vol,
            "tolerance": tolerance,
            "diff": (bag.net_volume or 0) - (target_vol or 0)
        }
    }


@router.post("/prebatch-recs/force-verify-ingredient")
def force_verify_ingredient(data: RecheckBagRequest, db: Session = Depends(get_db)):
    """Force verify all bags for a specific ingredient in a batch."""
    if not data.batch_id:
        raise HTTPException(status_code=400, detail="batch_id is required")
        
    re_code = data.bag_barcode # Using bag_barcode field to pass re_code
    now = datetime.now()
    
    # 1. Update all PreBatchRecs for this batch and re_code
    reqs = db.query(models.PreBatchReq).filter(
        models.PreBatchReq.batch_id == data.batch_id,
        models.PreBatchReq.re_code == re_code
    ).all()
    
    recs_updated = 0
    for req in reqs:
        recs = db.query(models.PreBatchRec).filter(
            models.PreBatchRec.req_id == req.id
        ).all()
        for r in recs:
            r.recheck_status = 1
            r.recheck_at = now
            r.recheck_by = data.operator
            recs_updated += 1
            
    # 2. Update ALL PreBatchItems with this re_code in the batch
    items = db.query(models.PreBatchItem).filter(
        models.PreBatchItem.batch_id == data.batch_id,
        models.PreBatchItem.re_code == re_code
    ).all()
    
    for item in items:
        item.recheck_status = 1
        item.recheck_at = now
        item.recheck_by = data.operator
        
    db.commit()
    
    return {
        "status": "OK",
        "message": f"Verified ingredient {re_code} ({recs_updated} bags, {len(items)} items)",
        "re_code": re_code
    }


@router.post("/prebatch-items/repair-overwrite-bug")
def repair_overwrite_bug(plan_id: Optional[str] = None, db: Session = Depends(get_db)):
    """Repair data corrupted by the pack_item overwrite bug.
    
    Finds PreBatchItems where:
    - status == 2 (incorrectly marked complete)
    - net_volume < required_volume (only last package's weight was kept)
    - No matching PreBatchRec records exist (old code didn't create them)
    
    Resets these items so operators can re-weigh the missing packages.
    """
    query = db.query(models.PreBatchItem).filter(
        models.PreBatchItem.status == 2,
        models.PreBatchItem.net_volume.isnot(None),
    )
    if plan_id:
        query = query.filter(models.PreBatchItem.plan_id == plan_id)
    
    items = query.all()
    repaired = []
    
    for item in items:
        net = float(item.net_volume or 0)
        req = float(item.required_volume or 0)
        
        # Skip items where net_volume is close to or exceeds required_volume
        if req > 0 and net >= req * 0.95:
            continue
        
        # Check if PreBatchRec records exist for this item's req
        req_obj = db.query(models.PreBatchReq).filter(
            models.PreBatchReq.batch_id == item.batch_id,
            models.PreBatchReq.re_code == item.re_code,
        ).first()
        
        rec_count = 0
        if req_obj:
            rec_count = db.query(models.PreBatchRec).filter(
                models.PreBatchRec.req_id == req_obj.id,
            ).count()
        
        # If no recs exist and net < required, this item was corrupted
        if rec_count == 0 and net < req * 0.95:
            old_status = item.status
            old_net = item.net_volume
            
            # Reset: clear net_volume to 0 so operator re-weighs from scratch
            item.status = 0  # Back to Wait
            item.net_volume = None
            item.batch_record_id = None
            item.package_no = None
            item.total_packages = None
            item.prebatch_id = None
            item.packing_status = 0
            
            # Also reset the PreBatchReq status
            if req_obj:
                req_obj.status = 0
            
            # Reset batch.batch_prepare if it was auto-finalized
            batch = db.query(models.ProductionBatch).filter(
                models.ProductionBatch.id == item.batch_db_id
            ).first()
            if batch and batch.batch_prepare:
                batch.batch_prepare = False
                if batch.status == "Prepared":
                    batch.status = "In-Progress"
            
            repaired.append({
                "item_id": item.id,
                "batch_id": item.batch_id,
                "re_code": item.re_code,
                "old_status": old_status,
                "old_net_volume": float(old_net or 0),
                "required_volume": req,
                "action": "reset to Wait — operator must re-weigh all packages",
            })
    
    db.commit()
    return {
        "repaired_count": len(repaired),
        "repaired_items": repaired,
    }

@router.patch("/production-batches/{batch_id}/release")
def release_batch_to_production(batch_id: str, db: Session = Depends(get_db)):
    """
    Final approval for a box/batch. 
    Only permits if all bags are re-checked OK.
    """
    batch = db.query(models.ProductionBatch).filter(models.ProductionBatch.batch_id == batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")

    bags = db.query(models.PreBatchRec).filter(
        models.PreBatchRec.batch_record_id.like(f"{batch_id}%")
    ).all()

    if not bags:
        raise HTTPException(status_code=400, detail="No bags found for this batch to verify")

    all_ok = all(b.recheck_status == 1 for b in bags)
    
    if not all_ok:
        pending_count = sum(1 for b in bags if b.recheck_status != 1)
        raise HTTPException(
            status_code=400, 
            detail=f"Re-check incomplete. {pending_count} bag(s) still pending or have errors."
        )

    batch.ready_to_product = True
    batch.status = "Ready for Production"
    db.commit()

    return {"status": "success", "message": "Batch released to production"}


@router.post("/sync-prebatch-wh")
def sync_prebatch_warehouse(db: Session = Depends(get_db)):
    """Sync all prebatch_reqs.wh from ingredient master warehouse field.
    Also normalizes SSP→SPP and sets empty warehouses to MIX."""
    # Step 0: Normalize SSP → SPP everywhere
    r0a = db.execute(text("UPDATE ingredients SET warehouse = 'SPP' WHERE warehouse = 'SSP'"))
    r0b = db.execute(text("UPDATE prebatch_reqs SET wh = 'SPP' WHERE wh = 'SSP'"))
    # Step 1: Set empty ingredient warehouses to MIX
    r1 = db.execute(text("""
        UPDATE ingredients SET warehouse = 'MIX'
        WHERE warehouse IS NULL OR warehouse = ''
    """))
    # Step 2: Sync prebatch_reqs.wh from ingredient master
    r2 = db.execute(text("""
        UPDATE prebatch_reqs pr
        JOIN ingredients i ON pr.re_code = i.re_code
        SET pr.wh = i.warehouse
        WHERE i.warehouse IS NOT NULL AND i.warehouse != '' AND pr.wh != i.warehouse
    """))
    db.commit()
    return {
        "status": "success",
        "ssp_to_spp": r0a.rowcount + r0b.rowcount,
        "ingredients_set_to_mix": r1.rowcount,
        "prebatch_reqs_synced": r2.rowcount
    }


# ═══════════════════════════════════════════════════════════════
# Label Archive — Save & Reprint from file
# ═══════════════════════════════════════════════════════════════
import os
from pydantic import BaseModel

LABEL_ARCHIVE_ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "x91-labelArchive")


class LabelArchiveRequest(BaseModel):
    label_type: str  # e.g. "prebatch-label", "packingbox-label"
    label_id: str    # e.g. "P260311-02-02-001-FV044A-1"
    svg_content: str
    metadata: Optional[dict] = None


@router.post("/labels/archive")
def archive_label(req: LabelArchiveRequest):
    """Save a label SVG to the archive folder."""
    now = datetime.now()
    date_folder = now.strftime("%Y-%m-%d")
    time_prefix = now.strftime("%H%M%S")
    safe_id = req.label_id.replace("/", "_").replace("\\", "_")
    
    folder = os.path.join(LABEL_ARCHIVE_ROOT, req.label_type, date_folder)
    os.makedirs(folder, exist_ok=True)
    
    filename = f"{time_prefix}_{safe_id}.svg"
    filepath = os.path.join(folder, filename)
    
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(req.svg_content)
    
    # Save metadata JSON alongside
    if req.metadata:
        import json
        meta_path = filepath.replace(".svg", ".json")
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump({**req.metadata, "archived_at": now.isoformat(), "label_id": req.label_id}, f, indent=2, default=str)
    
    return {
        "status": "saved",
        "path": f"{req.label_type}/{date_folder}/{filename}",
        "archived_at": now.isoformat()
    }


@router.get("/labels/archive")
def list_archived_labels(label_type: Optional[str] = None, date: Optional[str] = None):
    """List archived labels, optionally filtered by type and date."""
    results = []
    if not os.path.exists(LABEL_ARCHIVE_ROOT):
        return results
    
    types = [label_type] if label_type else os.listdir(LABEL_ARCHIVE_ROOT)
    for lt in types:
        lt_path = os.path.join(LABEL_ARCHIVE_ROOT, lt)
        if not os.path.isdir(lt_path):
            continue
        dates = [date] if date else sorted(os.listdir(lt_path), reverse=True)
        for d in dates:
            d_path = os.path.join(lt_path, d)
            if not os.path.isdir(d_path):
                continue
            for f in sorted(os.listdir(d_path)):
                if f.endswith(".svg"):
                    results.append({
                        "label_type": lt,
                        "date": d,
                        "filename": f,
                        "path": f"{lt}/{d}/{f}",
                    })
    return results


@router.get("/labels/archive/file/{label_type}/{date}/{filename}")
def get_archived_label(label_type: str, date: str, filename: str):
    """Get a specific archived label SVG content."""
    filepath = os.path.join(LABEL_ARCHIVE_ROOT, label_type, date, filename)
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="Label not found")
    with open(filepath, "r", encoding="utf-8") as f:
        return {"svg": f.read(), "path": f"{label_type}/{date}/{filename}"}


@router.delete("/prebatch-items/clear-plan/{plan_id}")
def clear_plan_prebatch(plan_id: str, fix_fv052a: bool = False, db: Session = Depends(get_db)):
    """Clear ALL prebatch data for a plan: recs, origins, items reset, batch flags reset."""
    from sqlalchemy import text as sql_t

    # 0. Delete prebatch_rec_from
    rec_from_deleted = db.execute(sql_t("""
        DELETE f FROM prebatch_rec_from f
        JOIN prebatch_recs r ON f.prebatch_rec_id = r.id
        WHERE r.plan_id = :p
    """), {"p": plan_id}).rowcount

    # 1. Delete prebatch_recs
    recs_deleted = db.execute(sql_t("DELETE FROM prebatch_recs WHERE plan_id = :p"), {"p": plan_id}).rowcount

    # 2. Delete origins
    origins_deleted = db.execute(sql_t("""
        DELETE f FROM prebatch_item_from f
        JOIN prebatch_items i ON f.prebatch_item_id = i.id
        WHERE i.plan_id = :p
    """), {"p": plan_id}).rowcount

    # 3. Reset all items
    items_reset = db.execute(sql_t("""
        UPDATE prebatch_items SET
            batch_record_id=NULL, net_volume=NULL, package_no=1, total_packages=1,
            intake_lot_id=NULL, mat_sap_code=NULL, prebatch_id=NULL, recode_batch_id=NULL,
            total_volume=NULL, total_request_volume=NULL, weighed_at=NULL,
            recheck_status=0, packing_status=0, status=0
        WHERE plan_id = :p
    """), {"p": plan_id}).rowcount

    # 4. Fix FV052A if requested
    fv_fixed = 0
    if fix_fv052a:
        fv_fixed = db.execute(sql_t("""
            UPDATE prebatch_items SET required_volume = 7.5
            WHERE plan_id = :p AND re_code = 'FV052A' AND required_volume = 10.0
        """), {"p": plan_id}).rowcount

    # 5. Reset prebatch_reqs
    reqs_reset = db.execute(sql_t("""
        UPDATE prebatch_reqs SET status = 0
        WHERE batch_id LIKE :bp
    """), {"bp": plan_id + "%"}).rowcount

    # 6. Reset batch flags
    batches_reset = db.execute(sql_t("""
        UPDATE production_batches SET batch_prepare = 0, status = 'In-Progress'
        WHERE batch_id LIKE :bp AND batch_prepare = 1
    """), {"bp": plan_id + "%"}).rowcount

    db.commit()
    return {
        "status": "success",
        "plan_id": plan_id,
        "recs_deleted": recs_deleted,
        "origins_deleted": origins_deleted,
        "items_reset": items_reset,
        "fv052a_fixed": fv_fixed,
        "reqs_reset": reqs_reset,
        "batches_reset": batches_reset,
    }


# =============================================================================
# PRODUCTION LOGGING & QC RECORDS
# =============================================================================

class StepLogRequest(BaseModel):
    batch_id: str
    phase_id: Optional[str] = None
    step_id: int
    action_code: Optional[str] = None
    re_code: Optional[str] = None
    target_value: Optional[float] = None
    actual_value: Optional[float] = None
    operator: Optional[str] = "unknown"

class QcRecordRequest(BaseModel):
    batch_id: str
    step_id: int
    brix_target: Optional[float] = None
    brix_actual: float
    ph_target: Optional[float] = None
    ph_actual: float
    operator: Optional[str] = "unknown"

@router.post("/production-batches/{batch_id_str}/log-step")
def log_production_step(batch_id_str: str, log_data: StepLogRequest, db: Session = Depends(get_db)):
    """Log a completed step from the PLC into the database history."""
    try:
        new_log = models.ProductionStepLog(
            batch_id=batch_id_str,
            phase_id=log_data.phase_id,
            step_id=log_data.step_id,
            action_code=log_data.action_code,
            re_code=log_data.re_code,
            target_value=log_data.target_value,
            actual_value=log_data.actual_value,
            operator=log_data.operator
        )
        db.add(new_log)
        db.commit()
        return {"status": "success", "message": f"Step {log_data.step_id} logged successfully"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/production-batches/{batch_id_str}/qc-record")
def save_qc_record(batch_id_str: str, qc_data: QcRecordRequest, db: Session = Depends(get_db)):
    """Save QC data (Brix/pH) entered by the operator for a specific step."""
    try:
        new_qc = models.ProductionQcRecord(
            batch_id=batch_id_str,
            step_id=qc_data.step_id,
            brix_target=qc_data.brix_target,
            brix_actual=qc_data.brix_actual,
            ph_target=qc_data.ph_target,
            ph_actual=qc_data.ph_actual,
            operator=qc_data.operator
        )
        db.add(new_qc)
        db.commit()
        return {"status": "success", "message": "QC data saved successfully"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/production-batches/{batch_id_str}/logs")
def get_production_step_logs(batch_id_str: str, db: Session = Depends(get_db)):
    """
    Return sku_steps recipe rows with actual values merged from logs.
    Ensures temperature/agitator/destination always show from recipe.
    Falls back to log-only rows when no recipe exists for the SKU.
    """
    logs = db.query(models.ProductionStepLog).filter(
        models.ProductionStepLog.batch_id == batch_id_str
    ).order_by(models.ProductionStepLog.completed_at.asc()).all()

    qc_records = db.query(models.ProductionQcRecord).filter(
        models.ProductionQcRecord.batch_id == batch_id_str
    ).all()

    batch_row = db.query(models.ProductionBatch).filter(
        models.ProductionBatch.batch_id == batch_id_str
    ).first()
    sku_id = batch_row.sku_id if batch_row else None

    action_map: dict = {str(ac.action_code): ac.action_description
                        for ac in db.query(models.SkuAction).all()}

    # Build phase description map from sku_phases table
    # e.g. D1010 → 'ละลาย ingredient', A1010 → 'Mixing'
    phase_desc_map: dict = {}
    try:
        from sqlalchemy import text as _text
        rows = db.execute(_text("SELECT phase_code, phase_description FROM sku_phases")).fetchall()
        for r in rows:
            phase_desc_map[str(r[0])] = r[1]
    except Exception:
        pass

    # Build recipe lookup: index sku_steps by BOTH phase_id AND phase_number
    # KEY FIX: phase_number in sku_steps is 'p0010' but logs use 'p010'
    # Normalize by removing extra leading zeros: p0010 → p010, p0020 → p020
    import re as _re
    def norm_pnum(s: str) -> str:
        return _re.sub(r'^(p)(0+)', lambda m: m.group(1), s) if s else s

    recipe_map: dict = {}
    if sku_id:
        for ss in db.query(models.SkuStep).filter(models.SkuStep.sku_id == sku_id).all():
            pid   = str(ss.phase_id    or '').strip()
            pnum  = str(ss.phase_number or '').strip()
            pnorm = norm_pnum(pnum)   # p0010 → p010
            sub   = ss.sub_step
            if pid:   recipe_map[(pid,   sub)] = ss
            if pnum:  recipe_map[(pnum,  sub)] = ss
            if pnorm and pnorm != pnum:
                recipe_map[(pnorm, sub)] = ss  # p010 key for legacy log match

    def fmt_ts(dt):
        return dt.isoformat() if dt else None

    result_logs = []
    for log in logs:
        pid = str(log.phase_id or '').strip()
        # Try all possible recipe matches (raw, normalized)
        recipe = (recipe_map.get((pid, log.step_id)) or
                  recipe_map.get((norm_pnum(pid), log.step_id)))
        result_logs.append({
            "phase_id":           log.phase_id,
            "phase_description":  phase_desc_map.get(str(log.phase_id or '').strip())
                                  or (phase_desc_map.get(str(recipe.phase_id or '').strip()) if recipe else None)
                                  or '',
            "sub_step":           log.step_id,
            "action_code":        log.action_code,
            "action":             recipe.action             if recipe else None,
            "action_description": (recipe.action_description if recipe else None)
                                  or action_map.get(str(log.action_code or '')),
            "re_code":            log.re_code or (recipe.re_code if recipe else None),
            "target_value":       log.target_value or (recipe.require if recipe else None),
            "actual_value":       log.actual_value,
            "uom":                (recipe.uom if recipe else None) or "kg",
            "temperature":        recipe.temperature    if recipe else None,
            "agitator_rpm":       recipe.agitator_rpm   if recipe else None,
            "hi_shear_rpm":       recipe.high_shear_rpm if recipe else None,
            "destination":        recipe.destination    if recipe else None,
            "step_condition":     recipe.step_condition if recipe else None,
            "low_tol":            recipe.low_tol        if recipe else None,
            "high_tol":           recipe.high_tol       if recipe else None,
            "completed_at":       fmt_ts(log.completed_at),
            "operator":           log.operator,
            "operator2":          None,
        })

    return {
        "batch_id":   batch_id_str,
        "sku_id":     sku_id,
        "logs":       result_logs,
        "qc_records": [
            {
                "id":          qc.id,
                "batch_id":    qc.batch_id,
                "step_id":     qc.step_id,
                "brix_target": qc.brix_target,
                "brix_actual": qc.brix_actual,
                "brix_ok":     (abs(qc.brix_actual - qc.brix_target) <= 0.5)
                               if (qc.brix_actual is not None and qc.brix_target is not None) else None,
                "ph_target":   qc.ph_target,
                "ph_actual":   qc.ph_actual,
                "ph_ok":       (abs(qc.ph_actual - qc.ph_target) <= 0.1)
                               if (qc.ph_actual is not None and qc.ph_target is not None) else None,
                "recorded_at": fmt_ts(qc.recorded_at),
                "operator":    qc.operator,
            }
            for qc in qc_records
        ],
    }


# ── REQ-1: Sub-Batch Runs (A, B, C per batch) ────────────────────────────────

@router.get("/production-batches/{batch_id_str}/sub-batches")
def get_sub_batches(batch_id_str: str, db: Session = Depends(get_db)):
    rows = db.query(models.ProductionSubBatch).filter(
        models.ProductionSubBatch.batch_id == batch_id_str
    ).order_by(models.ProductionSubBatch.sub_run.asc()).all()
    return rows


class SubBatchCreate(BaseModel):
    sub_run: str
    actual_volume: Optional[float] = None
    start_time: Optional[str] = None
    stop_time: Optional[str] = None
    remarks: Optional[str] = None
    operator: Optional[str] = None


@router.post("/production-batches/{batch_id_str}/sub-batches")
def upsert_sub_batch(batch_id_str: str, body: SubBatchCreate, db: Session = Depends(get_db)):
    from datetime import datetime
    def parse_ts(s): return datetime.fromisoformat(s.replace("Z", "+00:00")) if s else None
    existing = db.query(models.ProductionSubBatch).filter(
        models.ProductionSubBatch.batch_id == batch_id_str,
        models.ProductionSubBatch.sub_run == body.sub_run
    ).first()
    try:
        if existing:
            existing.actual_volume = body.actual_volume
            existing.start_time    = parse_ts(body.start_time)
            existing.stop_time     = parse_ts(body.stop_time)
            existing.remarks       = body.remarks
            existing.operator      = body.operator
        else:
            db.add(models.ProductionSubBatch(
                batch_id=batch_id_str, sub_run=body.sub_run,
                actual_volume=body.actual_volume,
                start_time=parse_ts(body.start_time),
                stop_time=parse_ts(body.stop_time),
                remarks=body.remarks, operator=body.operator
            ))
        db.commit()
        return {"status": "ok", "sub_run": body.sub_run}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/production-batches/{batch_id_str}/sub-batches/{sub_run}")
def delete_sub_batch(batch_id_str: str, sub_run: str, db: Session = Depends(get_db)):
    row = db.query(models.ProductionSubBatch).filter(
        models.ProductionSubBatch.batch_id == batch_id_str,
        models.ProductionSubBatch.sub_run == sub_run
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="Sub-batch not found")
    db.delete(row)
    db.commit()
    return {"status": "deleted"}
