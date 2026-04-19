from database import SessionLocal
import models
from sqlalchemy import func

def fix_steps():
    db = SessionLocal()
    source_sku = "SKU-CONCEPT-01"
    target_sku = "SKU-CONCEPT-01-001"

    # Check if target is empty
    count = db.query(models.SkuStep).filter(models.SkuStep.sku_id == target_sku).count()
    if count > 0:
        print(f"Target SKU {target_sku} already has {count} steps. Aborting.")
        return

    # Check source
    steps = db.query(models.SkuStep).filter(models.SkuStep.sku_id == source_sku).all()
    if not steps:
        print(f"Source SKU {source_sku} has no steps. Aborting.")
        return

    print(f"Copying {len(steps)} steps from {source_sku} to {target_sku}...")
    
    for step in steps:
        new_step = models.SkuStep(
            sku_id=target_sku,
            phase_number=step.phase_number,
            phase_id=step.phase_id,
            master_step=step.master_step,
            sub_step=step.sub_step,
            action=step.action,
            re_code=step.re_code,
            action_code=step.action_code,
            setup_step=step.setup_step,
            destination=step.destination,
            require=step.require,
            uom=step.uom,
            low_tol=step.low_tol,
            high_tol=step.high_tol,
            step_condition=step.step_condition,
            agitator_rpm=step.agitator_rpm,
            high_shear_rpm=step.high_shear_rpm,
            temperature=step.temperature,
            temp_low=step.temp_low,
            temp_high=step.temp_high,
            step_time=step.step_time,
            step_timer_control=step.step_timer_control,
            qc_temp=step.qc_temp,
            record_steam_pressure=step.record_steam_pressure,
            record_ctw=step.record_ctw,
            operation_brix_record=step.operation_brix_record,
            operation_ph_record=step.operation_ph_record,
            brix_sp=step.brix_sp,
            ph_sp=step.ph_sp,
            action_description=step.action_description
        )
        db.add(new_step)
    
    db.commit()
    print("Done copying steps.")

if __name__ == "__main__":
    fix_steps()
