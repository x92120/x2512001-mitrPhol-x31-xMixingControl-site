import sys, os
from sqlalchemy import text
sys.path.insert(0, os.path.dirname(__file__))
from database import engine

def list_plans():
    with engine.connect() as conn:
        result = conn.execute(text("SELECT plan_id, sku_id, status FROM production_plans ORDER BY id DESC LIMIT 5"))
        print("Last 5 plans in DB:")
        for row in result:
            print(f"PlanID: {row[0]}, SKU: {row[1]}, Status: {row[2]}")

if __name__ == "__main__":
    list_plans()
