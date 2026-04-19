"""
Generate sample Production Plan with Freshly SKU Group for testing.
"""
import sys, os
from datetime import datetime, date

# Add current dir to path to import local modules
sys.path.insert(0, os.path.dirname(__file__))

from database import SessionLocal
from models import SkuGroup, Sku, SkuStep, ProductionPlan, ProductionBatch, PreBatchItem, Ingredient

def generate_sample_data():
    db = SessionLocal()
    try:
        # 1. Create Freshly SKU Group
        group_code = "FRESHLY"
        group_name = "Freshly SKU Group"
        freshly_group = db.query(SkuGroup).filter(SkuGroup.group_code == group_code).first()
        if not freshly_group:
            freshly_group = SkuGroup(
                group_code=group_code,
                group_name=group_name,
                description="Sample group for freshly production testing",
                status="Active"
            )
            db.add(freshly_group)
            db.commit()
            db.refresh(freshly_group)
            print(f"✅ Created SkuGroup: {group_name}")
        else:
            print(f"ℹ️ SkuGroup {group_name} already exists")

        # 2. Create a specific SKU
        sku_id = "SKU-FR-TEST-01"
        sku_name = "Freshly Berry Mix 500kg"
        sku = db.query(Sku).filter(Sku.sku_id == sku_id).first()
        if not sku:
            sku = Sku(
                sku_id=sku_id,
                sku_name=sku_name,
                std_batch_size=500.0,
                uom="kg",
                status="Active",
                sku_group=freshly_group.id,  # Use ID because the column is an INTEGER in the DB
                creat_by="system"
            )
            db.add(sku)
            db.commit()
            db.refresh(sku)
            print(f"✅ Created SKU: {sku_name}")
        else:
            print(f"ℹ️ SKU {sku_name} already exists")

        # 3. Create SKU Steps
        # Cleanup old steps for this SKU to ensure fresh test
        db.query(SkuStep).filter(SkuStep.sku_id == sku_id).delete()
        
        steps = [
            # Phase 1: Preparation
            SkuStep(sku_id=sku_id, phase_number="1", phase_id="A1010", sub_step=10, action="RO Water Batching", action_description="RO Water Batching", require=200.0, uom="kg", action_code="10101"),
            SkuStep(sku_id=sku_id, phase_number="1", phase_id="A1010", sub_step=20, action="Heating to 60C", action_description="Heating to 60C", temperature=60.0, temp_low=58.0, temp_high=62.0, action_code="30101"),
            
            # Phase 2: Ingredients
            SkuStep(sku_id=sku_id, phase_number="2", phase_id="D1010", sub_step=10, action="Add Sugar Premix", action_description="Add Sugar Premix", re_code="SPP01", require=50.0, low_tol=49.5, high_tol=50.5, action_code="20101"),
            SkuStep(sku_id=sku_id, phase_number="2", phase_id="D1010", sub_step=20, action="Dissolve for 10 min", action_description="Dissolve for 10 min", step_time=10, agitator_rpm=400.0, action_code="30102"),
            
            # Phase 3: Flavour
            SkuStep(sku_id=sku_id, phase_number="3", phase_id="A1020", sub_step=10, action="High Shear Mixing", action_description="High Shear Mixing", high_shear_rpm=1500.0, step_time=5, action_code="30103"),
            SkuStep(sku_id=sku_id, phase_number="3", phase_id="A1020", sub_step=20, action="Add Berry Flavor", action_description="Add Berry Flavor", re_code="FH01", require=2.5, low_tol=2.45, high_tol=2.55, action_code="20201"),
            
            # Phase 4: QC
            SkuStep(sku_id=sku_id, phase_number="4", phase_id="x1030", sub_step=10, action="QC Check Brix/pH", action_description="QC Check Brix/pH", operation_brix_record=True, operation_ph_record=True, brix_sp="12.5", ph_sp="3.5", action_code="40101"),
        ]
        db.add_all(steps)
        db.commit()
        print(f"✅ Added {len(steps)} steps for SKU {sku_id}")

        # 4. Create Production Plan
        plan_id = f"PL-FRESH-{datetime.now().strftime('%y%m%d-%H%M')}"
        plan = ProductionPlan(
            plan_id=plan_id,
            sku_id=sku_id,
            sku_name=sku_name,
            plant="02", # Mixing 2
            total_volume=1000.0,
            batch_size=500.0,
            num_batches=2,
            start_date=date.today(),
            status="Planned",
            created_by="system"
        )
        db.add(plan)
        db.commit()
        db.refresh(plan)
        print(f"✅ Created Production Plan: {plan_id}")

        # 5. Create Batches
        for i in range(1, 3):
            batch_id = f"{plan_id}-{i:03d}"
            batch = ProductionBatch(
                plan_id=plan.id,
                batch_id=batch_id,
                sku_id=sku_id,
                plant="02",
                batch_size=500.0,
                status="Created"
            )
            db.add(batch)
            db.commit()
            db.refresh(batch)
            print(f"   🔹 Created Batch: {batch_id}")

            # 6. Create PreBatchItems (for ingredients in steps)
            for step in steps:
                if step.re_code:
                    # Find ingredient name
                    ing = db.query(Ingredient).filter(Ingredient.re_code == step.re_code).first()
                    ing_name = ing.name if ing else f"Ingredient {step.re_code}"
                    
                    wh = "SPP" if step.re_code.startswith("SPP") else ("FH" if step.re_code.startswith("FH") else "Mix")
                    
                    item = PreBatchItem(
                        batch_db_id=batch.id,
                        plan_id=plan_id,
                        batch_id=batch_id,
                        re_code=step.re_code,
                        ingredient_name=ing_name,
                        required_volume=step.require,
                        wh=wh,
                        status=0 # Wait
                    )
                    db.add(item)
            db.commit()
            print(f"      🔸 Added PreBatch requirements for batch {batch_id}")

        print("\n🎉 Sample production data generation complete!")
        print(f"Summary: Plan {plan_id} with 2 batches of SKU {sku_id}")

    except Exception as e:
        db.rollback()
        print(f"❌ Error generating data: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    generate_sample_data()
