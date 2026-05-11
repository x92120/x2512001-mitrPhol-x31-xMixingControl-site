from database import SessionLocal
from sqlalchemy import text

def main():
    db = SessionLocal()
    query = text("""
        SELECT sku_id, COUNT(*) as step_count 
        FROM sku_steps 
        GROUP BY sku_id 
        ORDER BY step_count DESC 
        LIMIT 5
    """)
    rows = db.execute(query).fetchall()
    
    print("Top SKUs by Step Count:")
    for r in rows:
        print(f"SKU: {r[0]}, Steps: {r[1]}")
        
    db.close()

if __name__ == "__main__":
    main()
