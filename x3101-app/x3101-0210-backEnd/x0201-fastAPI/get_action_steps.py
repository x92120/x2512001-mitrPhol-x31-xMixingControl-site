from database import SessionLocal
from sqlalchemy import text

def main():
    db = SessionLocal()
    
    # Query sample from sku_steps
    query = text("SELECT sku_id, step_number, action_code, set_point, target_value FROM sku_steps LIMIT 15")
    rows = db.execute(query).fetchall()
    
    # Query count
    count = db.execute(text("SELECT COUNT(*) FROM sku_steps")).scalar()
    
    print(f"Total rows in sku_steps: {count}")
    print(f"{'sku_id':<15} | {'step_number':<15} | {'action_code':<15} | {'set_point':<10} | {'target_value':<10}")
    print("-" * 75)
    for r in rows:
        print(f"{str(r[0]):<15} | {str(r[1]):<15} | {str(r[2]):<15} | {str(r[3]):<10} | {str(r[4]):<10}")
        
    db.close()

if __name__ == "__main__":
    main()
