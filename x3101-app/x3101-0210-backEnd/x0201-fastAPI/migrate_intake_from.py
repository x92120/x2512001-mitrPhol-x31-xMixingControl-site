from sqlalchemy import create_engine, text
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

DB_USER = os.getenv("DB_USER", "mixingcontrol")
DB_PASSWORD = os.getenv("DB_PASSWORD", "admin100")
DB_PORT = os.getenv("DB_PORT", "3306")
DB_NAME = os.getenv("DB_NAME", "xMixingControl")

CLOUD_HOST = os.getenv("CLOUD_DB", "152.42.166.150")
REMOTE_HOST = os.getenv("REMOTE_DB", "192.168.121.11")

def migrate_db(host, label):
    print(f"\n--- Migrating Database: {label} ({host}) ---")
    url = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{host}:{DB_PORT}/{DB_NAME}"
    try:
        engine = create_engine(url)
        with engine.connect() as connection:
            # 1. Create ingredient_intake_from table
            print("Creating ingredient_intake_from table...")
            connection.execute(text("""
                CREATE TABLE IF NOT EXISTS ingredient_intake_from (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    name VARCHAR(100) UNIQUE NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """))
            
            # 2. Add some default initial data
            print("Seeding initial data...")
            cursor = connection.execute(text("SELECT COUNT(*) FROM ingredient_intake_from"))
            count = cursor.scalar()
            if count == 0:
                connection.execute(text("INSERT INTO ingredient_intake_from (name) VALUES ('Warehouse'), ('Store'), ('Production')"))

            # 3. Rename column warehouse_location to intake_from
            print("Renaming warehouse_location to intake_from...")
            # Check if column exists first
            cursor = connection.execute(text("""
                SELECT count(*) FROM information_schema.columns 
                WHERE table_name = 'ingredient_intake_lists' 
                AND column_name = 'warehouse_location'
                AND table_schema = :db_name
            """), {"db_name": DB_NAME})
            if cursor.scalar() > 0:
                connection.execute(text("ALTER TABLE ingredient_intake_lists CHANGE warehouse_location intake_from VARCHAR(50)"))
                print("Column renamed successfully.")
            else:
                print("Column warehouse_location not found, checking if intake_from exists...")
                cursor = connection.execute(text("""
                    SELECT count(*) FROM information_schema.columns 
                    WHERE table_name = 'ingredient_intake_lists' 
                    AND column_name = 'intake_from'
                    AND table_schema = :db_name
                """), {"db_name": DB_NAME})
                if cursor.scalar() == 0:
                     connection.execute(text("ALTER TABLE ingredient_intake_lists ADD intake_from VARCHAR(50)"))
                     print("Column intake_from added.")
                else:
                    print("Column intake_from already exists.")
            
            connection.commit()
            print(f"✅ {label} migrated successfully.")
    except Exception as e:
        print(f"❌ Error migrating {label}: {e}")

if __name__ == "__main__":
    migrate_db(REMOTE_HOST, "Remote DB")
    migrate_db(CLOUD_HOST, "Cloud DB")
