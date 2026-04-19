from database import engine
from sqlalchemy import text
import sys

def check_duplicates():
    try:
        with engine.connect() as conn:
            # Check duplicates
            query = text("SELECT intake_lot_id, COUNT(*) as cnt FROM ingredient_intake_lists GROUP BY intake_lot_id HAVING cnt > 1")
            res = conn.execute(query).fetchall()
            if res:
                print("Found duplicates:")
                for r in res:
                    print(f"ID: {r[0]}, Count: {r[1]}")
            else:
                print("No duplicates found.")
            
            # Try to add UNIQUE index
            print("Attempting to add UNIQUE index...")
            try:
                conn.execute(text("CREATE UNIQUE INDEX idx_intake_lot_id_unique ON ingredient_intake_lists (intake_lot_id)"))
                conn.commit()
                print("Successfully added UNIQUE index.")
            except Exception as ex:
                print(f"Failed to add UNIQUE index: {ex}")
                
    except Exception as e:
        print(f"Database error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    check_duplicates()
