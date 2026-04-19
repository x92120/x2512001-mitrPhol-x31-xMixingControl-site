import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
from database import Base
import models  # Important to import models to register with Base

# Load environment variables
load_dotenv()

DB_USER = os.getenv("DB_USER", "mixingcontrol")
DB_PASSWORD = os.getenv("DB_PASSWORD", "admin100")
DB_PORT = os.getenv("DB_PORT", "3306")
DB_NAME = os.getenv("DB_NAME", "xMixingControl")

# The hosts we want to sync
HOSTS = {
    "REMOTE_DB": os.getenv("REMOTE_DB", "192.168.121.11"),
    "CLOUD_DB": os.getenv("CLOUD_DB", "152.42.166.150")
}

def sync_host(name, host):
    url = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{host}:{DB_PORT}/{DB_NAME}"
    print(f"\n--- Syncing {name} ({host}) ---")
    
    try:
        engine = create_engine(url)
        # 1. Create all missing tables
        print("Ensuring all tables exist...")
        Base.metadata.create_all(bind=engine)
        
        # 2. Add missing columns to prebatch_recs (manual migration for existing tables)
        with engine.connect() as conn:
            # Check for mat_sap_code in prebatch_recs
            print("Checking prebatch_recs columns...")
            columns_to_add = [
                ("prebatch_id", "VARCHAR(100) AFTER intake_lot_id"),
                ("recode_batch_id", "VARCHAR(50) AFTER prebatch_id"),
                ("mat_sap_code", "VARCHAR(50) AFTER intake_lot_id")
            ]
            
            for col_name, col_def in columns_to_add:
                result = conn.execute(text(f"SHOW COLUMNS FROM prebatch_recs LIKE '{col_name}'"))
                if not result.fetchone():
                    print(f"Adding column '{col_name}' to prebatch_recs...")
                    conn.execute(text(f"ALTER TABLE prebatch_recs ADD COLUMN {col_name} {col_def}"))
                    conn.execute(text(f"CREATE INDEX ix_prebatch_recs_{col_name} ON prebatch_recs ({col_name})"))
                    conn.commit()
                else:
                    print(f"Column '{col_name}' already exists.")

            # Check for batch_prepare_vol and std_package_size in ingredient_intake_lists
            print("Checking ingredient_intake_lists columns...")
            intake_cols = [
                ("batch_prepare_vol", "FLOAT AFTER manufacturing_date"),
                ("std_package_size", "FLOAT DEFAULT 25.0 AFTER batch_prepare_vol"),
                ("po_number", "VARCHAR(50) AFTER edit_at"),
                ("manufacturing_date", "DATETIME AFTER po_number")
            ]
            for col_name, col_def in intake_cols:
                result = conn.execute(text(f"SHOW COLUMNS FROM ingredient_intake_lists LIKE '{col_name}'"))
                if not result.fetchone():
                    print(f"Adding column '{col_name}' to ingredient_intake_lists...")
                    conn.execute(text(f"ALTER TABLE ingredient_intake_lists ADD COLUMN {col_name} {col_def}"))
                    conn.commit()
                else:
                    print(f"Column '{col_name}' already exists.")

        print(f"Successfully synced {name}.")
    except Exception as e:
        print(f"Error syncing {name}: {e}")

if __name__ == "__main__":
    for name, host in HOSTS.items():
        if host:
            sync_host(name, host)
        else:
            print(f"Skip {name}: Host not defined.")
