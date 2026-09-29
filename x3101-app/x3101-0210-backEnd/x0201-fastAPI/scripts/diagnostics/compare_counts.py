import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

DB_USER = os.getenv("DB_USER", "mixingcontrol")
DB_PASSWORD = os.getenv("DB_PASSWORD", "admin100")
DB_PORT = os.getenv("DB_PORT", "3306")
DB_NAME = os.getenv("DB_NAME", "xMixingControl")

CLOUD_HOST = os.getenv("CLOUD_DB", "152.42.166.150")
REMOTE_HOST = os.getenv("REMOTE_DB", "192.168.121.11")

TABLES = [
    "users",
    "plants",
    "warehouses",
    "ingredients",
    "sku_masters",
    "sku_phases",
    "sku_steps",
    "sku_actions",
    "sku_destinations",
    "production_plans",
    "production_batches",
    "ingredient_intake_lists",
    "intake_package_receive",
    "ingredient_intake_history",
    "prebatch_reqs",
    "prebatch_recs"
]

def get_counts(host):
    url = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{host}:{DB_PORT}/{DB_NAME}"
    engine = create_engine(url)
    counts = {}
    try:
        with engine.connect() as conn:
            for table in TABLES:
                try:
                    res = conn.execute(text(f"SELECT COUNT(*) FROM {table}"))
                    counts[table] = res.scalar()
                except:
                    counts[table] = "Error/Missing"
    except Exception as e:
        return f"Error connecting to {host}: {e}"
    return counts

if __name__ == "__main__":
    print("Fetching row counts...")
    cloud_counts = get_counts(CLOUD_HOST)
    remote_counts = get_counts(REMOTE_HOST)
    
    print(f"\n{'Table Name':<30} | {'Cloud (Source)':<15} | {'Remote (Target)':<15}")
    print("-" * 65)
    for table in TABLES:
        c = cloud_counts.get(table, "N/A")
        r = remote_counts.get(table, "N/A")
        print(f"{table:<30} | {str(c):<15} | {str(r):<15}")
