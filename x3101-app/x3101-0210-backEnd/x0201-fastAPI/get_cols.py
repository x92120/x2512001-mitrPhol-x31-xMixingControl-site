from database import SessionLocal
from sqlalchemy import text

def main():
    db = SessionLocal()
    query = text("SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'sku_steps' AND TABLE_SCHEMA = DATABASE()")
    cols = db.execute(query).fetchall()
    print("Columns in sku_steps:")
    for c in cols:
        print(f"- {c[0]}")
    db.close()

if __name__ == "__main__":
    main()
