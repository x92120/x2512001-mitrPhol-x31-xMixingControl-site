from database import SessionLocal
from sqlalchemy import text
import sys

def main():
    db = SessionLocal()
    query = text("SELECT action_code, action_description FROM sku_actions ORDER BY action_code;")
    try:
        results = db.execute(query).fetchall()
        print("ACTION_CODE|ACTION_DESCRIPTION")
        for row in results:
            print(f"{row[0]}|{row[1]}")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    main()
