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

def clear_db(host, label):
    print(f"\n--- Clearing Database: {label} ({host}) ---")
    url = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{host}:{DB_PORT}/{DB_NAME}"
    try:
        engine = create_engine(url)
        tables = [
            "prebatch_recs",
            "prebatch_reqs",
            "production_batches",
            "production_plan_history",
            "production_plans"
        ]
        
        with engine.connect() as connection:
            connection.execute(text("SET FOREIGN_KEY_CHECKS = 0;"))
            for table in tables:
                print(f"Clearing table: {table}")
                connection.execute(text(f"DELETE FROM {table};"))
                connection.execute(text(f"ALTER TABLE {table} AUTO_INCREMENT = 1;"))
            connection.execute(text("SET FOREIGN_KEY_CHECKS = 1;"))
            connection.commit()
            print(f"✅ {label} cleared successfully.")
    except Exception as e:
        print(f"❌ Error clearing {label}: {e}")

if __name__ == "__main__":
    # Clear both Cloud and Remote to ensure a fresh start
    clear_db(REMOTE_HOST, "Remote DB")
    clear_db(CLOUD_HOST, "Cloud DB")
