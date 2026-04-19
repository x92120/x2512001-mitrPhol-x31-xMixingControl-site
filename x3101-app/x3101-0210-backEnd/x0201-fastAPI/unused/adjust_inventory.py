from database import SessionLocal
import models
from sqlalchemy import func

def adjust_inventory():
    db = SessionLocal()
    print("Starting inventory adjustment based on existing PreBatch records...")
    
    try:
        # 1. Reset all remain_vol to intake_vol first? 
        # Or better: just calculate what SHOULD be deducted.
        # User said "update or adjust intake inventory for all"
        
        inventory_items = db.query(models.IngredientIntakeList).all()
        
        adjusted_count = 0
        for item in inventory_items:
            # Calculate total volume consumed by PreBatch records for this lot
            total_consumed = db.query(func.sum(models.PreBatchRec.net_volume)).filter(
                models.PreBatchRec.intake_lot_id == item.intake_lot_id,
                models.PreBatchRec.re_code == item.re_code
            ).scalar() or 0
            
            # TODO: also consider other types of consumption if any (e.g. direct production)
            # For now, we focus on PreBatch as requested.
            
            target_remain = item.intake_vol - total_consumed
            
            if item.remain_vol != target_remain:
                # print(f"Adjusting {item.intake_lot_id} ({item.re_code}): {item.remain_vol} -> {target_remain}")
                item.remain_vol = target_remain
                adjusted_count += 1
        
        db.commit()
        print(f"Done. Adjusted {adjusted_count} inventory lots.")
        
    except Exception as e:
        db.rollback()
        print(f"Error during adjustment: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    adjust_inventory()
