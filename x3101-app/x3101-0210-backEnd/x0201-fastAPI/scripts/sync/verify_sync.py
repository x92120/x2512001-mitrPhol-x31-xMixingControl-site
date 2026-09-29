import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

DB_USER = os.getenv("DB_USER", "mixingcontrol")
DB_PASSWORD = os.getenv("DB_PASSWORD", "admin100")
DB_PORT = os.getenv("DB_PORT", "3306")
DB_NAME = os.getenv("DB_NAME", "xMixingControl")

HOSTS = {
    "REMOTE_DB": os.getenv("REMOTE_DB", "192.168.121.11"),
    "CLOUD_DB": os.getenv("CLOUD_DB", "152.42.166.150")
}

def verify_host(name, host):
    url = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{host}:{DB_PORT}/{DB_NAME}"
    print(f"\n--- Verifying {name} ({host}) ---")
    
    try:
        engine = create_engine(url)
        with engine.connect() as conn:
            # Check for tables
            tables = ["ingredient_intake_lists", "intake_package_receive", "prebatch_recs", "warehouses", "plants", "sku_masters"]
            print("Tables sanity check:")
            for t in tables:
                res = conn.execute(text(f"SHOW TABLES LIKE '{t}'"))
                exists = "EXISTS" if res.fetchone() else "MISSING"
                print(f"  - {t}: {exists}")
                
            # Check for columns in ingredient_intake_lists
            print("ingredient_intake_lists columns:")
            cols = ["batch_prepare_vol", "std_package_size", "po_number", "manufacturing_date"]
            for c in cols:
                res = conn.execute(text(f"SHOW COLUMNS FROM ingredient_intake_lists LIKE '{c}'"))
                exists = "EXISTS" if res.fetchone() else "MISSING"
                print(f"  - {c}: {exists}")

            # Check for views
            views = ["v_sku_master_detail", "v_sku_step_detail", "v_sku_complete"]
            print("Views sanity check:")
            for v in views:
                # In MySQL, SHOW FULL TABLES shows BASE TABLE or VIEW
                res = conn.execute(text(f"SHOW FULL TABLES LIKE '{v}'"))
                row = res.fetchone()
                if row:
                    table_type = row[1] # second column is Table_type
                    print(f"  - {v}: {table_type}")
                else:
                    print(f"  - {v}: MISSING")

    except Exception as e:
        print(f"Error verifying {name}: {e}")

if __name__ == "__main__":
    for name, host in HOSTS.items():
        if host:
            verify_host(name, host)
