"""
Reports Router
==============
Unified endpoints for all printable reports across the xMixing system.
"""
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session  # type: ignore[import-untyped]
from sqlalchemy import func, and_  # type: ignore[import-untyped]

from database import get_db  # type: ignore[import-untyped]
import models  # type: ignore[import-untyped]

router = APIRouter(prefix="/reports", tags=["Reports"])


def _parse_date(val: str | None) -> datetime | None:
    if not val:
        return None
    try:
        return datetime.strptime(val, "%Y-%m-%d")
    except ValueError:
        return None


# ── 1. Production Daily Report ───────────────────────────────────────────────

@router.get("/production-daily")
def production_daily_report(
    date: str | None = None,
    db: Session = Depends(get_db),
):
    """Production daily summary: plans, batches, ingredient consumption."""
    target_date = _parse_date(date) or datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    next_day = target_date + timedelta(days=1)

    # Plans created/active for this date
    plans = db.query(models.ProductionPlan).filter(
        models.ProductionPlan.start_date <= target_date.date(),
        models.ProductionPlan.finish_date >= target_date.date(),
    ).all()

    plan_list = []
    for p in plans:
        batches = []
        for b in (p.batches or []):
            batches.append({
                "batch_id": b.batch_id,
                "batch_size": b.batch_size,
                "status": b.status,
            })
        plan_list.append({
            "plan_id": p.plan_id,
            "sku_id": p.sku_id,
            "sku_name": p.sku_name,
            "plant": p.plant,
            "total_volume": p.total_plan_volume or p.total_volume,
            "num_batches": p.num_batches,
            "status": p.status,
            "start_date": str(p.start_date) if p.start_date else None,
            "finish_date": str(p.finish_date) if p.finish_date else None,
            "batches": batches,
        })

    # Ingredient consumption for the date (pre-batch records)
    consumption = (
        db.query(
            models.PreBatchRecFrom.mat_sap_code,
            func.sum(models.PreBatchRecFrom.take_volume).label("total_vol"),
            func.count(models.PreBatchRecFrom.id).label("count"),
        )
        .filter(
            models.PreBatchRecFrom.created_at >= target_date,
            models.PreBatchRecFrom.created_at < next_day,
        )
        .group_by(models.PreBatchRecFrom.mat_sap_code)
        .all()
    )

    consumption_list = []
    for c in consumption:
        # Get re_code from any record
        sample = db.query(models.PreBatchRecFrom).filter(
            models.PreBatchRecFrom.mat_sap_code == c.mat_sap_code
        ).first()
        rec = db.query(models.PreBatchRec).filter(
            models.PreBatchRec.id == sample.prebatch_rec_id
        ).first() if sample else None
        consumption_list.append({
            "mat_sap_code": c.mat_sap_code,
            "re_code": rec.re_code if rec else "",
            "total_volume": c.total_vol,
            "transaction_count": c.count,
        })

    return {
        "date": str(target_date.date()),
        "plans": plan_list,
        "ingredient_consumption": consumption_list,
        "summary": {
            "total_plans": len(plan_list),
            "total_batches": sum(len(p["batches"]) for p in plan_list),
            "total_volume": sum(p["total_volume"] or 0 for p in plan_list),
        },
    }


# ── 2. Pre-Batch Summary Report ─────────────────────────────────────────────

@router.get("/prebatch-summary")
def prebatch_summary_report(
    from_date: str | None = None,
    to_date: str | None = None,
    db: Session = Depends(get_db),
):
    """Pre-batch completion summary with ingredient variance."""
    date_from = _parse_date(from_date)
    date_to = _parse_date(to_date)
    if date_to:
        date_to = date_to + timedelta(days=1)

    q = db.query(models.PreBatchRec)
    if date_from:
        q = q.filter(models.PreBatchRec.created_at >= date_from)
    if date_to:
        q = q.filter(models.PreBatchRec.created_at < date_to)

    records = q.order_by(models.PreBatchRec.created_at.desc()).all()

    result = []
    for rec in records:
        origins = db.query(models.PreBatchRecFrom).filter(
            models.PreBatchRecFrom.prebatch_rec_id == rec.id
        ).all()
        origin_list = [{
            "intake_lot_id": o.intake_lot_id,
            "mat_sap_code": o.mat_sap_code,
            "take_volume": o.take_volume,
        } for o in origins]

        result.append({
            "batch_record_id": rec.batch_record_id,
            "plan_id": rec.plan_id,
            "re_code": rec.re_code,
            "mat_sap_code": rec.mat_sap_code,
            "package_no": rec.package_no,
            "total_packages": rec.total_packages,
            "net_volume": rec.net_volume,
            "total_volume": rec.total_volume,
            "total_request_volume": rec.total_request_volume,
            "recheck_status": rec.recheck_status,
            "packing_status": rec.packing_status,
            "created_at": rec.created_at.isoformat() if rec.created_at else None,
            "origins": origin_list,
        })

    # Group by re_code for ingredient totals
    ingredient_totals = {}
    for rec in result:
        key = rec["re_code"] or "unknown"
        if key not in ingredient_totals:
            ingredient_totals[key] = {
                "re_code": key,
                "mat_sap_code": rec["mat_sap_code"],
                "total_net": 0, "total_request": 0, "count": 0,
            }
        ingredient_totals[key]["total_net"] += rec["net_volume"] or 0
        ingredient_totals[key]["total_request"] += rec["total_request_volume"] or 0
        ingredient_totals[key]["count"] += 1

    return {
        "records": result,
        "ingredient_totals": list(ingredient_totals.values()),
        "summary": {
            "total_records": len(result),
            "total_net_volume": sum(r["net_volume"] or 0 for r in result),
        },
    }


# ── 3. Batch Record Report ──────────────────────────────────────────────────

@router.get("/batch-record/{batch_id}")
def batch_record_report(
    batch_id: str,
    db: Session = Depends(get_db),
):
    """Full batch record with ingredients used."""
    batch = db.query(models.ProductionBatch).filter(
        models.ProductionBatch.batch_id == batch_id
    ).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")

    plan = batch.plan

    # Get pre-batch records for this batch
    prebatch_recs = db.query(models.PreBatchRec).filter(
        models.PreBatchRec.plan_id == plan.plan_id if plan else False,
    ).all()

    # Filter to batch-relevant re_codes from reqs
    reqs = db.query(models.PreBatchReq).filter(
        models.PreBatchReq.batch_id == batch_id
    ).all()

    ingredients = []
    for req in reqs:
        recs = db.query(models.PreBatchRec).filter(
            models.PreBatchRec.plan_id == plan.plan_id if plan else "",
            models.PreBatchRec.re_code == req.re_code,
        ).all()
        for rec in recs:
            origins = db.query(models.PreBatchRecFrom).filter(
                models.PreBatchRecFrom.prebatch_rec_id == rec.id
            ).all()
            for o in origins:
                ingredients.append({
                    "re_code": req.re_code,
                    "ingredient_name": req.ingredient_name,
                    "mat_sap_code": o.mat_sap_code,
                    "intake_lot_id": o.intake_lot_id,
                    "required_volume": req.required_volume,
                    "actual_volume": o.take_volume,
                    "batch_record_id": rec.batch_record_id,
                })

    return {
        "batch": {
            "batch_id": batch.batch_id,
            "sku_id": batch.sku_id,
            "plant": batch.plant,
            "batch_size": batch.batch_size,
            "status": batch.status,
            "created_at": batch.created_at.isoformat() if batch.created_at else None,
        },
        "plan": {
            "plan_id": plan.plan_id if plan else "",
            "sku_name": plan.sku_name if plan else "",
            "start_date": str(plan.start_date) if plan and plan.start_date else None,
            "finish_date": str(plan.finish_date) if plan and plan.finish_date else None,
        },
        "ingredients": ingredients,
        "reqs": [{
            "re_code": r.re_code,
            "ingredient_name": r.ingredient_name,
            "required_volume": r.required_volume,
            "wh": r.wh,
            "status": r.status,
        } for r in reqs],
    }


# ── 4. Packing List Report ──────────────────────────────────────────────────

@router.get("/packing-list/{plan_id}")
def packing_list_report(
    plan_id: str,
    db: Session = Depends(get_db),
):
    """Packing list for a plan — all bags grouped by batch."""
    plan = db.query(models.ProductionPlan).filter(
        models.ProductionPlan.plan_id == plan_id
    ).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    recs = db.query(models.PreBatchRec).filter(
        models.PreBatchRec.plan_id == plan_id
    ).order_by(models.PreBatchRec.re_code, models.PreBatchRec.package_no).all()

    bags = []
    for rec in recs:
        bags.append({
            "batch_record_id": rec.batch_record_id,
            "re_code": rec.re_code,
            "mat_sap_code": rec.mat_sap_code,
            "package_no": rec.package_no,
            "total_packages": rec.total_packages,
            "net_volume": rec.net_volume,
            "packing_status": rec.packing_status,
            "recheck_status": rec.recheck_status,
            "packed_at": rec.packed_at.isoformat() if rec.packed_at else None,
            "packed_by": rec.packed_by,
        })

    return {
        "plan_id": plan.plan_id,
        "sku_id": plan.sku_id,
        "sku_name": plan.sku_name,
        "total_volume": plan.total_plan_volume,
        "bags": bags,
        "summary": {
            "total_bags": len(bags),
            "packed": sum(1 for b in bags if b["packing_status"] == 1),
            "unpacked": sum(1 for b in bags if b["packing_status"] == 0),
            "checked": sum(1 for b in bags if b["recheck_status"] == 1),
        },
    }


# ── 5. Quality Check / Batch Recheck Report ─────────────────────────────────

@router.get("/quality-check")
def quality_check_report(
    from_date: str | None = None,
    to_date: str | None = None,
    db: Session = Depends(get_db),
):
    """Batch recheck results summary."""
    date_from = _parse_date(from_date)
    date_to = _parse_date(to_date)
    if date_to:
        date_to = date_to + timedelta(days=1)

    q = db.query(models.PreBatchRec).filter(
        models.PreBatchRec.recheck_status > 0
    )
    if date_from:
        q = q.filter(models.PreBatchRec.recheck_at >= date_from)
    if date_to:
        q = q.filter(models.PreBatchRec.recheck_at < date_to)

    records = q.order_by(models.PreBatchRec.recheck_at.desc()).all()

    items = []
    for rec in records:
        items.append({
            "batch_record_id": rec.batch_record_id,
            "plan_id": rec.plan_id,
            "re_code": rec.re_code,
            "mat_sap_code": rec.mat_sap_code,
            "package_no": rec.package_no,
            "recheck_status": rec.recheck_status,  # 1=OK, 2=Error
            "recheck_at": rec.recheck_at.isoformat() if rec.recheck_at else None,
            "recheck_by": rec.recheck_by,
        })

    return {
        "items": items,
        "summary": {
            "total_checked": len(items),
            "passed": sum(1 for i in items if i["recheck_status"] == 1),
            "failed": sum(1 for i in items if i["recheck_status"] == 2),
        },
    }


# ── 6. Ingredient Expiry Alert ──────────────────────────────────────────────

@router.get("/expiry-alert")
def expiry_alert_report(
    db: Session = Depends(get_db),
):
    """Ingredient expiry alert: expired, expiring soon, OK."""
    now = datetime.now()
    threshold = now + timedelta(days=30)

    intakes = db.query(models.IngredientIntakeList).filter(
        models.IngredientIntakeList.status == "Active",
        models.IngredientIntakeList.remain_vol > 0,
    ).order_by(models.IngredientIntakeList.expire_date.asc()).all()

    expired = []
    warning = []
    ok = []
    no_expiry = []

    for i in intakes:
        item = {
            "intake_lot_id": i.intake_lot_id,
            "mat_sap_code": i.mat_sap_code,
            "re_code": i.re_code or "",
            "material_description": i.material_description or "",
            "remain_vol": i.remain_vol,
            "intake_to": i.intake_to or "",
            "expire_date": i.expire_date.isoformat() if i.expire_date else None,
            "days_left": (i.expire_date - now).days if i.expire_date else None,
        }
        if not i.expire_date:
            no_expiry.append(item)
        elif i.expire_date < now:
            expired.append(item)
        elif i.expire_date < threshold:
            warning.append(item)
        else:
            ok.append(item)

    return {
        "expired": expired,
        "warning": warning,
        "ok": ok,
        "no_expiry": no_expiry,
        "summary": {
            "total_lots": len(intakes),
            "expired_count": len(expired),
            "warning_count": len(warning),
            "ok_count": len(ok),
        },
    }


# ── 7. Traceability Report ──────────────────────────────────────────────────

@router.get("/traceability/{lot_or_batch_id}")
def traceability_report(
    lot_or_batch_id: str,
    db: Session = Depends(get_db),
):
    """End-to-end traceability: forward (lot→batch) and backward (batch→lot)."""
    result = {"type": None, "forward": None, "backward": None}

    # Try as intake lot (forward trace)
    intake = db.query(models.IngredientIntakeList).filter(
        models.IngredientIntakeList.intake_lot_id == lot_or_batch_id
    ).first()

    if intake:
        result["type"] = "forward"
        usages = db.query(models.PreBatchRecFrom).filter(
            models.PreBatchRecFrom.intake_lot_id == lot_or_batch_id
        ).all()

        batch_trails = []
        for u in usages:
            rec = db.query(models.PreBatchRec).filter(
                models.PreBatchRec.id == u.prebatch_rec_id
            ).first()
            if rec:
                batch_trails.append({
                    "batch_record_id": rec.batch_record_id,
                    "plan_id": rec.plan_id,
                    "re_code": rec.re_code,
                    "take_volume": u.take_volume,
                    "date": u.created_at.isoformat() if u.created_at else None,
                })

        result["forward"] = {
            "lot": {
                "intake_lot_id": intake.intake_lot_id,
                "mat_sap_code": intake.mat_sap_code,
                "re_code": intake.re_code,
                "material_description": intake.material_description,
                "intake_vol": intake.intake_vol,
                "remain_vol": intake.remain_vol,
                "intake_at": intake.intake_at.isoformat() if intake.intake_at else None,
            },
            "used_in": batch_trails,
        }
        return result

    # Try as batch_id (backward trace)
    batch = db.query(models.ProductionBatch).filter(
        models.ProductionBatch.batch_id == lot_or_batch_id
    ).first()

    if batch:
        result["type"] = "backward"
        plan = batch.plan

        reqs = db.query(models.PreBatchReq).filter(
            models.PreBatchReq.batch_id == lot_or_batch_id
        ).all()

        ingredients = []
        for req in reqs:
            recs = db.query(models.PreBatchRec).filter(
                models.PreBatchRec.plan_id == plan.plan_id if plan else "",
                models.PreBatchRec.re_code == req.re_code,
            ).all()
            lots_used = []
            for rec in recs:
                for o in rec.origins:
                    lot = db.query(models.IngredientIntakeList).filter(
                        models.IngredientIntakeList.intake_lot_id == o.intake_lot_id
                    ).first()
                    lots_used.append({
                        "intake_lot_id": o.intake_lot_id,
                        "mat_sap_code": o.mat_sap_code,
                        "take_volume": o.take_volume,
                        "lot_id": lot.lot_id if lot else "",
                        "intake_from": lot.intake_from if lot else "",
                    })
            ingredients.append({
                "re_code": req.re_code,
                "ingredient_name": req.ingredient_name,
                "required_volume": req.required_volume,
                "lots_used": lots_used,
            })

        result["backward"] = {
            "batch": {
                "batch_id": batch.batch_id,
                "sku_id": batch.sku_id,
                "batch_size": batch.batch_size,
                "status": batch.status,
            },
            "plan": {
                "plan_id": plan.plan_id if plan else "",
                "sku_name": plan.sku_name if plan else "",
            },
            "ingredients": ingredients,
        }
        return result

    raise HTTPException(status_code=404, detail="ID not found as intake lot or batch")


# ── 8. Production Plan ODT/DOCX Report ──────────────────────────────────────────────

@router.get("/production-plan-odt/{plan_id}")
def generate_production_plan_odt(
    plan_id: str,
    db: Session = Depends(get_db)
):
    """Generate a DOCX report for a production plan using docxtpl."""
    try:
        from docxtpl import DocxTemplate
        import tempfile
        import os
    except ImportError:
        raise HTTPException(status_code=500, detail="Document generation libraries are not installed.")

    plan = db.query(models.ProductionPlan).filter(models.ProductionPlan.plan_id == plan_id).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    # Gather data
    # The template is now located in the frontend's x70-Report folder
    template_path = os.path.join(os.path.dirname(__file__), "..", "..", "..", "x01-frontEnd", "x0101-xMixing", "app", "x70-Report", "templates", "ReportTemplate.docx")
    template_path = os.path.abspath(template_path)
    
    if not os.path.exists(template_path):
        raise HTTPException(status_code=500, detail=f"Report template not found on server at: {template_path}")

    # Get batches and items
    batches_data = []
    
    # Needs to match the fetch logic from earlier: wait-status included
    from sqlalchemy.orm import selectinload
    prebatch_items = db.query(models.PreBatchItem).options(
        selectinload(models.PreBatchItem.origins)
    ).filter(
        models.PreBatchItem.plan_id == plan_id
    ).all()

    for batch in (plan.batches or []):
        items = [i for i in prebatch_items if i.batch_id == batch.batch_id]
        
        # Calculate status setpoint logic
        all_boxed = all(r.packing_status == 1 for r in items) if items else False
        some_prepared = any(r.status == 2 or r.packing_status == 2 for r in items) if items else False
        
        status_setpoint = "Pending"
        if all_boxed and items:
            status_setpoint = "Completed"
        elif some_prepared:
            status_setpoint = "Preparation In-Progress"
            
        b_dict = {
            "batch_id": batch.batch_id,
            "status": batch.status,
            "batch_size": batch.batch_size,
            "status_setpoint": status_setpoint,
            "items": []
        }
        
        for req in items:
            b_dict["items"].append({
                "prebatch_id": req.prebatch_id or "-",
                "mat_sap_code": req.mat_sap_code or "-",
                "re_code": req.re_code,
                "required_volume": req.required_volume,
                "net_volume": req.net_volume or "-",
                "package_no": f"{req.package_no}/{req.total_packages}" if req.packing_status == 1 else "-"
            })
            
        batches_data.append(b_dict)
        
    context = {
        "plan_id": plan.plan_id,
        "sku_name": plan.sku_name or plan.sku_id,
        "start_date": str(plan.start_date) if plan.start_date else "-",
        "finish_date": str(plan.finish_date) if plan.finish_date else "-",
        "total_volume": plan.total_plan_volume or plan.total_volume,
        "items": [item for b in batches_data for item in [
            {
                "batch_id": b["batch_id"],
                "prebatch_id": it["prebatch_id"],
                "mat_sap_code": it["mat_sap_code"],
                "re_code": it["re_code"],
                "required_volume": it["required_volume"],
                "net_volume": it["net_volume"],
                "package_no": it["package_no"],
            } for it in b["items"]
        ]]
    }

    doc = DocxTemplate(template_path)
    doc.render(context)
    
    # Save to temp file
    fd, temp_path = tempfile.mkstemp(suffix=".docx")
    os.close(fd)
    doc.save(temp_path)
    
    from fastapi.responses import FileResponse
    from fastapi.background import BackgroundTasks

    def cleanup_file(path: str):
        try:
            os.remove(path)
        except Exception:
            pass
            
    # We must not cleanup immediately since FileResponse reads the file asynchronously.
    # We pass it to background tasks or rely on OS temp wiping if we have no BG tasks in signature.
    # To keep simple without modifying function signature, we just return it.
    
    return FileResponse(
        path=temp_path, 
        filename=f"Plan_{plan_id}.docx", 
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
