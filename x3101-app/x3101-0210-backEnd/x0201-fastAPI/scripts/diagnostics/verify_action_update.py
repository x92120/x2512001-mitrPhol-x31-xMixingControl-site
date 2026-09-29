from database import SessionLocal
from sqlalchemy import text

def main():
    db = SessionLocal()

    print("--- Database Update Report ---")
    
    # 1. Check the sku_actions table
    action_info = db.execute(text("SELECT action_code, action_description FROM sku_actions WHERE action_code = '21010'")).fetchone()
    if action_info:
        print(f"Action Code: {action_info[0]}")
        print(f"Description: {action_info[1]}")
    else:
        print("Action 21010 not found in sku_actions!")
        
    print("\n--- Rows Updated to 21010 ---")
    
    # 2. Check all tables with action or action_code
    query = text("""
        SELECT TABLE_NAME, COLUMN_NAME 
        FROM INFORMATION_SCHEMA.COLUMNS 
        WHERE TABLE_SCHEMA = DATABASE() 
        AND COLUMN_NAME IN ('action_code', 'action')
        AND TABLE_NAME NOT LIKE 'v_%'
    """)
    columns = db.execute(query).fetchall()

    for table, column in columns:
        if table == 'sku_actions':
            continue
        try:
            count = db.execute(text(f"SELECT COUNT(*) FROM {table} WHERE {column} = '21010'")).scalar()
            if count > 0:
                print(f"Table `{table}` (column `{column}`): {count} rows")
        except Exception as e:
            pass

    db.close()

if __name__ == "__main__":
    main()
