from database import SessionLocal
from sqlalchemy import text

def main():
    db = SessionLocal()

    print("Starting update process...")

    # 1. Insert new action code 21010
    try:
        db.execute(text("""
            INSERT INTO sku_actions (action_code, action_description, created_at, updated_at)
            SELECT '21010', 'Manual Add to Mixing Tank', NOW(), NOW()
            FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM sku_actions WHERE action_code = '21010')
        """))
        db.commit()
        print("Ensured 21010 exists.")
    except Exception as e:
        db.rollback()
        print(f"Error inserting 21010: {e}")

    # 2. Update description of 21010
    try:
        db.execute(text("UPDATE sku_actions SET action_description = 'Manual Add to Mixing Tank' WHERE action_code = '21010'"))
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"Error updating description for 21010: {e}")

    # 3. Find all tables with action_code or action and update them.
    try:
        query = text("""
            SELECT TABLE_NAME, COLUMN_NAME 
            FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_SCHEMA = DATABASE() 
            AND COLUMN_NAME IN ('action_code', 'action')
        """)
        columns = db.execute(query).fetchall()

        for table, column in columns:
            print(f"Updating {table}.{column}...")
            try:
                db.execute(text(f"UPDATE {table} SET {column} = '21010' WHERE {column} = '30010'"))
                db.commit()
                print(f"  -> Successfully updated {table}.{column}")
            except Exception as e:
                db.rollback()
                print(f"  -> Error updating {table}.{column}: {e}")
    except Exception as e:
        print(f"Error querying schema columns: {e}")

    # 4. Finally, delete 30010 from sku_actions if no longer used
    try:
        db.execute(text("DELETE FROM sku_actions WHERE action_code = '30010'"))
        db.commit()
        print("Deleted 30010 from sku_actions.")
    except Exception as e:
        db.rollback()
        print(f"Could not delete 30010 (maybe still referenced?): {e}")

    db.close()
    print("Done.")

if __name__ == "__main__":
    main()
