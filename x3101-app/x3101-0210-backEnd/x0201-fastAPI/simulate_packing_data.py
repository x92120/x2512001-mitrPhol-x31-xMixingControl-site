"""
Simulate Production Plans with PreBatch Records for Packing List Testing
========================================================================
Creates:
  - 2 plans per line (Line-1, Line-2, Line-3) = 6 plans total
  - 4-10 batches per plan (randomized)
  - PreBatch requirements per batch (from SKU recipe)
  - PreBatch records (weighed bags) with mixed packing_status (0/1)

Usage:
  cd x02-BackEnd/x0201-fastAPI
  python simulate_packing_data.py
"""
import sys
import os
import random
from datetime import date, datetime

# Add current dir to path for local imports
sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv
load_dotenv()

from database import SessionLocal
import models

db = SessionLocal()

# ─── Config ──────────────────────────────────────────────────────────────────
LINES = ["Line-1", "Line-2", "Line-3"]
PLANS_PER_LINE = 2
MIN_BATCHES = 4
MAX_BATCHES = 10
TODAY = date.today()
DATE_STR = TODAY.strftime("%Y-%m-%d")

# Warehouses for ingredients (FH or SSP)
WH_OPTIONS = ["FH", "SSP", "FH", "SSP", "FH"]  # Bias toward more FH

def get_existing_skus():
    """Fetch existing SKUs that have recipe steps with re_codes."""
    skus = db.query(models.Sku).all()
    valid = []
    for sku in skus:
        steps_with_ingredients = [s for s in sku.steps if s.re_code]
        if len(steps_with_ingredients) >= 2:  # At least 2 ingredients
            valid.append(sku)
    return valid

def get_next_plan_sequence(plant: str) -> int:
    """Get next available plan sequence number."""
    from sqlalchemy import func
    prefix = f"sim-{plant}-{DATE_STR}-"
    max_id = db.query(func.max(models.ProductionPlan.plan_id)).filter(
        models.ProductionPlan.plan_id.like(f"{prefix}%")
    ).scalar()
    if max_id:
        try:
            return int(max_id.split("-")[-1]) + 1
        except ValueError:
            pass
    return 1

def create_plan(plant: str, sku: models.Sku, num_batches: int, seq: int):
    """Create a plan with batches, requirements, and prebatch records."""
    plan_id = f"sim-{plant}-{DATE_STR}-{seq:03d}"
    batch_size = sku.std_batch_size or 500.0

    print(f"  📋 Plan: {plan_id} | SKU: {sku.sku_id} ({sku.sku_name}) | {num_batches} batches")

    # Create plan
    db_plan = models.ProductionPlan(
        plan_id=plan_id,
        sku_id=sku.sku_id,
        sku_name=sku.sku_name,
        plant=plant,
        total_volume=batch_size * num_batches,
        total_plan_volume=batch_size * num_batches,
        batch_size=batch_size,
        num_batches=num_batches,
        start_date=TODAY,
        status="In-Progress",
        created_by="simulator",
    )
    db.add(db_plan)
    db.flush()

    # History
    db.add(models.ProductionPlanHistory(
        plan_db_id=db_plan.id,
        action="create",
        new_status="In-Progress",
        remarks="Simulated plan",
        changed_by="simulator",
    ))

    # Get ingredient template from SKU steps
    ingredient_template = {}
    for step in sku.steps:
        if not step.re_code:
            continue
        step_req = step.require or 0
        if sku.std_batch_size and sku.std_batch_size > 0:
            step_req = (step_req / sku.std_batch_size) * batch_size
        if step.re_code not in ingredient_template:
            ing = db.query(models.Ingredient).filter(models.Ingredient.re_code == step.re_code).first()
            wh = random.choice(WH_OPTIONS)
            ingredient_template[step.re_code] = {
                'qty': 0,
                'name': ing.name if ing else step.re_code,
                'wh': wh,
                'pkg_size': ing.std_package_size if ing else 25.0,
            }
        ingredient_template[step.re_code]['qty'] += step_req

    # Create batches
    for i in range(1, num_batches + 1):
        batch_id = f"{plan_id}-{i:03d}"

        # Randomly decide batch status (some prepared, some not)
        is_prepared = random.random() < 0.4
        batch_status = "Prepared" if is_prepared else "Created"

        db_batch = models.ProductionBatch(
            plan_id=db_plan.id,
            batch_id=batch_id,
            sku_id=sku.sku_id,
            plant=plant,
            batch_size=batch_size,
            status=batch_status,
            batch_prepare=is_prepared,
        )
        db.add(db_batch)
        db.flush()

        # Create requirements + records for each ingredient
        for re_code, info in ingredient_template.items():
            req_vol = round(info['qty'], 4)
            pkg_size = info['pkg_size'] or 25.0

            db_req = models.PreBatchReq(
                batch_db_id=db_batch.id,
                plan_id=plan_id,
                batch_id=batch_id,
                re_code=re_code,
                ingredient_name=info['name'],
                required_volume=req_vol,
                wh=info['wh'],
                status=2 if is_prepared else random.choice([0, 1, 1]),
            )
            db.add(db_req)
            db.flush()

            # Create prebatch records (weighed bags) if batch has done any work
            if db_req.status >= 1:
                num_packages = max(1, int(req_vol / pkg_size)) if pkg_size > 0 else 1
                for pkg_no in range(1, num_packages + 1):
                    pkg_vol = pkg_size if pkg_no < num_packages else round(req_vol - pkg_size * (num_packages - 1), 4)
                    pkg_vol = round(pkg_vol + random.uniform(-0.05, 0.05), 4)  # slight variance

                    record_id = f"{batch_id}-{re_code}-{pkg_no:03d}"

                    # Random packing status: packed (1) or waiting (0)
                    is_packed = random.random() < 0.5 if is_prepared else random.random() < 0.2

                    db_rec = models.PreBatchRec(
                        req_id=db_req.id,
                        batch_record_id=record_id,
                        plan_id=plan_id,
                        re_code=re_code,
                        package_no=pkg_no,
                        total_packages=num_packages,
                        net_volume=pkg_vol,
                        total_volume=req_vol,
                        total_request_volume=req_vol,
                        prebatch_id=f"{batch_id}{re_code}{pkg_no:03d}",
                        recode_batch_id=f"{re_code}{pkg_no:03d}",
                        recheck_status=1 if is_prepared else 0,
                        packing_status=1 if is_packed else 0,
                        packed_at=datetime.now() if is_packed else None,
                        packed_by="simulator" if is_packed else None,
                    )
                    db.add(db_rec)

        print(f"    📦 Batch {batch_id} — {batch_status} — {len(ingredient_template)} ingredients")

    return db_plan


def main():
    print("=" * 60)
    print("🏭 Packing List Simulation Data Generator")
    print("=" * 60)

    # Get existing SKUs
    skus = get_existing_skus()
    if not skus:
        print("❌ No SKUs with recipe steps found. Please create SKUs first.")
        return

    print(f"✅ Found {len(skus)} valid SKUs: {[s.sku_id for s in skus[:5]]}...")

    total_plans = 0
    total_batches = 0

    for line in LINES:
        print(f"\n🔧 === {line} ===")
        for p in range(PLANS_PER_LINE):
            sku = random.choice(skus)
            num_batches = random.randint(MIN_BATCHES, MAX_BATCHES)
            seq = get_next_plan_sequence(line) + p

            try:
                plan = create_plan(line, sku, num_batches, seq)
                total_plans += 1
                total_batches += num_batches
            except Exception as e:
                print(f"    ❌ Error creating plan: {e}")
                db.rollback()
                continue

    # Commit all
    try:
        db.commit()
        print(f"\n{'=' * 60}")
        print(f"✅ DONE! Created {total_plans} plans, {total_batches} batches")
        print(f"{'=' * 60}")
    except Exception as e:
        db.rollback()
        print(f"\n❌ Commit failed: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
