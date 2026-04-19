from sqlalchemy.orm import Session
from database import SessionLocal
import models

def recreate_tasks():
    db = SessionLocal()
    try:
        print("Starting recreation of PB Tasks for existing plans...")
        
        plans = db.query(models.ProductionPlan).all()
        print(f"Found {len(plans)} existing production plans.")

        for plan in plans:
            print(f"Processing Plan: {plan.plan_id}")
            sku = db.query(models.Sku).filter(models.Sku.sku_id == plan.sku_id).first()
            if not sku:
                continue
            
            recipe_steps = sku.steps
            std_batch_size = sku.std_batch_size or 0
            
            ingredient_info = {}
            for step in recipe_steps:
                if not step.re_code:
                    continue
                if step.re_code not in ingredient_info:
                    ing = db.query(models.Ingredient).filter(models.Ingredient.re_code == step.re_code).first()
                    ing_name = ing.name if ing else step.re_code
                    ingredient_info[step.re_code] = {'qty_per_std': (step.require or 0), 'name': ing_name}
                else:
                    ingredient_info[step.re_code]['qty_per_std'] += (step.require or 0)

            batches = db.query(models.ProductionBatch).filter(models.ProductionBatch.plan_id == plan.id).all()
            for batch in batches:
                existing_count = db.query(models.PreBatchReq).filter(models.PreBatchReq.batch_id == batch.batch_id).count()
                if existing_count > 0:
                    continue

                for re_code, info in ingredient_info.items():
                    req_vol = info['qty_per_std']
                    if std_batch_size > 0:
                        req_vol = (req_vol / std_batch_size) * batch.batch_size
                    
                    wh_loc = "-"
                    first_stock = db.query(models.IngredientIntakeList.warehouse_location).filter(
                        models.IngredientIntakeList.re_code == re_code
                    ).first()
                    if first_stock:
                        wh_loc = first_stock[0]

                    db_req = models.PreBatchReq(
                        batch_db_id=batch.id,
                        plan_id=plan.plan_id,
                        batch_id=batch.batch_id,
                        re_code=re_code,
                        ingredient_name=info['name'],
                        required_volume=round(req_vol, 4),
                        wh=wh_loc,
                        status=0
                    )
                    db.add(db_req)
            
            db.commit()
        print("Successfully recreated tasks.")
    except Exception as e:
        print(f"Error: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    recreate_tasks()
