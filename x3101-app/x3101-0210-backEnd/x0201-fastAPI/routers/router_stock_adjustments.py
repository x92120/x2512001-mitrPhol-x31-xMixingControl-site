"""
Stock Adjustment Router
========================
Endpoints for creating and listing stock adjustments.
Atomically updates remain_vol in ingredient_intake_lists.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session  # type: ignore[import-untyped]

from database import get_db  # type: ignore[import-untyped]
import models  # type: ignore[import-untyped]
import schemas  # type: ignore[import-untyped]

router = APIRouter(prefix="/stock-adjustments", tags=["Stock Adjustments"])


@router.get("/", response_model=list[schemas.StockAdjustment])
def list_adjustments(
    skip: int = 0,
    limit: int = 200,
    intake_lot_id: str | None = None,
    db: Session = Depends(get_db),
):
    """List stock adjustments with optional lot filter."""
    q = db.query(models.StockAdjustment).order_by(models.StockAdjustment.adjusted_at.desc())
    if intake_lot_id:
        q = q.filter(models.StockAdjustment.intake_lot_id == intake_lot_id)
    return q.offset(skip).limit(limit).all()


@router.post("/", response_model=schemas.StockAdjustment, status_code=201)
def create_adjustment(
    payload: schemas.StockAdjustmentCreate,
    db: Session = Depends(get_db),
):
    """Create a stock adjustment and atomically update remain_vol."""
    # 1. Look up the intake record
    intake = (
        db.query(models.IngredientIntakeList)
        .filter(models.IngredientIntakeList.intake_lot_id == payload.intake_lot_id)
        .first()
    )
    if not intake:
        raise HTTPException(status_code=404, detail=f"Lot '{payload.intake_lot_id}' not found")

    prev_vol = intake.remain_vol or 0.0

    # 2. Calculate new volume
    if payload.adjust_type == "increase":
        new_vol = prev_vol + payload.adjust_qty
    else:  # decrease
        new_vol = prev_vol - payload.adjust_qty
        if new_vol < 0:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot decrease by {payload.adjust_qty}. Current remain_vol is {prev_vol}",
            )

    # 3. Update remain_vol atomically
    intake.remain_vol = new_vol

    # 4. Create adjustment record
    adj = models.StockAdjustment(
        intake_lot_id=payload.intake_lot_id,
        mat_sap_code=intake.mat_sap_code,
        re_code=intake.re_code,
        material_description=intake.material_description,
        adjust_type=payload.adjust_type,
        adjust_reason=payload.adjust_reason,
        adjust_qty=payload.adjust_qty,
        prev_remain_vol=prev_vol,
        new_remain_vol=new_vol,
        remark=payload.remark,
        adjusted_by=payload.adjusted_by,
    )
    db.add(adj)
    db.commit()
    db.refresh(adj)
    return adj


# ── Lot Lookup (for the adjustment form) ────────────────────────────────────

@router.get("/lot-lookup/{lot_id}", response_model=schemas.LotLookup)
def lookup_lot(lot_id: str, db: Session = Depends(get_db)):
    """Look up an intake lot for stock adjustment form auto-fill."""
    intake = (
        db.query(models.IngredientIntakeList)
        .filter(models.IngredientIntakeList.intake_lot_id == lot_id)
        .first()
    )
    if not intake:
        raise HTTPException(status_code=404, detail=f"Lot '{lot_id}' not found")
    return intake


@router.get("/lot-search", response_model=list[schemas.LotLookup])
def search_lots(q: str = "", limit: int = 20, db: Session = Depends(get_db)):
    """Search intake lots by lot_id, mat_sap_code, or re_code."""
    if not q:
        return (
            db.query(models.IngredientIntakeList)
            .filter(models.IngredientIntakeList.status == "Active")
            .order_by(models.IngredientIntakeList.id.desc())
            .limit(limit)
            .all()
        )
    needle = f"%{q}%"
    return (
        db.query(models.IngredientIntakeList)
        .filter(
            models.IngredientIntakeList.status == "Active",
            (
                models.IngredientIntakeList.intake_lot_id.ilike(needle)
                | models.IngredientIntakeList.mat_sap_code.ilike(needle)
                | models.IngredientIntakeList.re_code.ilike(needle)
            ),
        )
        .order_by(models.IngredientIntakeList.id.desc())
        .limit(limit)
        .all()
    )


# ── Stock Movement (combined adjustments + pre-batch usage) ─────────────────

@router.get("/movements/")
def list_stock_movements(
    date_from: str | None = None,
    date_to: str | None = None,
    db: Session = Depends(get_db),
):
    """Get all stock movements: adjustments + pre-batch usage, ordered by date.
    
    date_from / date_to should be YYYY-MM-DD strings.
    """
    from datetime import datetime as dt
    movements = []

    # 1. Stock Adjustments
    adj_q = db.query(models.StockAdjustment).order_by(models.StockAdjustment.adjusted_at.desc())
    if date_from:
        adj_q = adj_q.filter(models.StockAdjustment.adjusted_at >= dt.strptime(date_from, "%Y-%m-%d"))
    if date_to:
        adj_q = adj_q.filter(models.StockAdjustment.adjusted_at <= dt.strptime(date_to + " 23:59:59", "%Y-%m-%d %H:%M:%S"))
    for a in adj_q.limit(500).all():
        movements.append({
            "movement_type": "adjustment",
            "date": a.adjusted_at.isoformat() if a.adjusted_at else None,
            "intake_lot_id": a.intake_lot_id,
            "mat_sap_code": a.mat_sap_code or "",
            "re_code": a.re_code or "",
            "material_description": a.material_description or "",
            "direction": a.adjust_type,  # 'increase' or 'decrease'
            "qty": a.adjust_qty,
            "prev_vol": a.prev_remain_vol,
            "new_vol": a.new_remain_vol,
            "reason": a.adjust_reason or "",
            "remark": a.remark or "",
            "user": a.adjusted_by or "",
            "reference": "",
        })

    # 2. Pre-batch usage (from prebatch_rec_from)
    prf_q = db.query(models.PreBatchRecFrom).order_by(models.PreBatchRecFrom.created_at.desc())
    if date_from:
        prf_q = prf_q.filter(models.PreBatchRecFrom.created_at >= dt.strptime(date_from, "%Y-%m-%d"))
    if date_to:
        prf_q = prf_q.filter(models.PreBatchRecFrom.created_at <= dt.strptime(date_to + " 23:59:59", "%Y-%m-%d %H:%M:%S"))
    for prf in prf_q.limit(500).all():
        # Get the parent PreBatchRec for batch info
        rec = db.query(models.PreBatchRec).filter(models.PreBatchRec.id == prf.prebatch_rec_id).first()
        batch_ref = rec.batch_record_id if rec else ""
        re_code = rec.re_code if rec else ""
        # Get ingredient name
        ing = db.query(models.Ingredient).filter(models.Ingredient.re_code == re_code).first() if re_code else None

        movements.append({
            "movement_type": "prebatch",
            "date": prf.created_at.isoformat() if prf.created_at else None,
            "intake_lot_id": prf.intake_lot_id,
            "mat_sap_code": prf.mat_sap_code or "",
            "re_code": re_code,
            "material_description": ing.name if ing else re_code,
            "direction": "decrease",
            "qty": prf.take_volume,
            "prev_vol": None,
            "new_vol": None,
            "reason": "Pre-batch",
            "remark": "",
            "user": "",
            "reference": batch_ref,
        })

    # Sort all by date descending
    movements.sort(key=lambda m: m["date"] or "", reverse=True)

    return movements


# ── Usage detail for a specific intake lot ──────────────────────────────────

@router.get("/usage/{lot_id}")
def get_lot_usage(lot_id: str, db: Session = Depends(get_db)):
    """Get all pre-batch usage records for a specific intake lot."""
    records = (
        db.query(models.PreBatchRecFrom)
        .filter(models.PreBatchRecFrom.intake_lot_id == lot_id)
        .order_by(models.PreBatchRecFrom.created_at.desc())
        .all()
    )
    result = []
    for prf in records:
        rec = db.query(models.PreBatchRec).filter(models.PreBatchRec.id == prf.prebatch_rec_id).first()
        batch_ref = rec.batch_record_id if rec else ""
        plan_id = rec.plan_id if rec else ""
        re_code = rec.re_code if rec else ""
        result.append({
            "id": prf.id,
            "batch_record_id": batch_ref,
            "plan_id": plan_id,
            "re_code": re_code,
            "take_volume": prf.take_volume,
            "created_at": prf.created_at.isoformat() if prf.created_at else None,
        })
    return result


# ── Ingredient Stock Summary Report ─────────────────────────────────────────

@router.get("/summary-report")
def get_summary_report(
    from_date: str | None = None,
    to_date: str | None = None,
    db: Session = Depends(get_db),
):
    """
    Get ingredient stock summary report grouped by warehouse (FH, SPP).
    Lists all ingredients with intake lots, stock details, and movements.
    """
    from datetime import datetime, timedelta
    from sqlalchemy import or_

    # Parse dates
    date_from = None
    date_to = None
    if from_date:
        try:
            date_from = datetime.strptime(from_date, "%Y-%m-%d")
        except ValueError:
            pass
    if to_date:
        try:
            date_to = datetime.strptime(to_date, "%Y-%m-%d") + timedelta(days=1)
        except ValueError:
            pass

    # Fetch intake records
    q = db.query(models.IngredientIntakeList).filter(
        models.IngredientIntakeList.status == "Active"
    )
    if date_from:
        q = q.filter(models.IngredientIntakeList.intake_at >= date_from)
    if date_to:
        q = q.filter(models.IngredientIntakeList.intake_at < date_to)

    intakes = q.order_by(
        models.IngredientIntakeList.intake_to,
        models.IngredientIntakeList.re_code,
        models.IngredientIntakeList.intake_at,
    ).all()

    # Build grouped result
    result = {}  # key: warehouse
    for intake in intakes:
        wh = intake.intake_to or "OTHER"

        # Fetch adjustments for this lot
        adjustments = (
            db.query(models.StockAdjustment)
            .filter(models.StockAdjustment.intake_lot_id == intake.intake_lot_id)
            .order_by(models.StockAdjustment.adjusted_at.desc())
            .all()
        )

        # Fetch pre-batch usage for this lot
        prebatch_usage = (
            db.query(models.PreBatchRecFrom)
            .filter(models.PreBatchRecFrom.intake_lot_id == intake.intake_lot_id)
            .order_by(models.PreBatchRecFrom.created_at.desc())
            .all()
        )

        adj_list = []
        for a in adjustments:
            adj_list.append({
                "type": a.adjust_type,
                "reason": a.adjust_reason,
                "qty": a.adjust_qty,
                "date": a.adjusted_at.isoformat() if a.adjusted_at else None,
                "by": a.adjusted_by,
            })

        usage_list = []
        total_used = 0.0
        for u in prebatch_usage:
            rec = db.query(models.PreBatchRec).filter(
                models.PreBatchRec.id == u.prebatch_rec_id
            ).first()
            usage_list.append({
                "batch_record_id": rec.batch_record_id if rec else "",
                "take_volume": u.take_volume,
                "date": u.created_at.isoformat() if u.created_at else None,
            })
            total_used += u.take_volume or 0

        lot_data = {
            "intake_lot_id": intake.intake_lot_id,
            "mat_sap_code": intake.mat_sap_code,
            "re_code": intake.re_code or "",
            "material_description": intake.material_description or "",
            "intake_vol": intake.intake_vol,
            "remain_vol": intake.remain_vol,
            "used_vol": total_used,
            "intake_at": intake.intake_at.isoformat() if intake.intake_at else None,
            "expire_date": intake.expire_date.isoformat() if intake.expire_date else None,
            "uom": intake.uom or "kg",
            "adjustments": adj_list,
            "prebatch_usage": usage_list,
            "adj_total": sum(
                a["qty"] if a["type"] == "increase" else -a["qty"]
                for a in adj_list
            ),
        }

        if wh not in result:
            result[wh] = []
        result[wh].append(lot_data)

    return result
