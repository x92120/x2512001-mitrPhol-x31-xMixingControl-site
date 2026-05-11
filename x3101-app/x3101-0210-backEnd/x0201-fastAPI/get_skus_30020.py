from database import SessionLocal
from sqlalchemy import text

def main():
    db = SessionLocal()
    
    query = text("SELECT DISTINCT sku_id FROM sku_steps WHERE action_code = '30020' ORDER BY sku_id")
    rows = db.execute(query).fetchall()
    
    print(f"Total distinct SKUs using 30020: {len(rows)}")
    for r in rows:
        print(f"- {r[0]}")
        
    db.close()

if __name__ == "__main__":
    main()
