import os
import pandas as pd
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

def sync_table(table_name):
    cloud_url = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{CLOUD_HOST}:{DB_PORT}/{DB_NAME}"
    remote_url = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{REMOTE_HOST}:{DB_PORT}/{DB_NAME}"
    
    cloud_engine = create_engine(cloud_url)
    remote_engine = create_engine(remote_url)
    
    print(f"Reading data from Cloud.{table_name}...")
    try:
        df = pd.read_sql_table(table_name, cloud_engine)
        print(f"Fetched {len(df)} rows.")
        
        with remote_engine.connect() as conn:
            print(f"Clearing Remote.{table_name}...")
            conn.execute(text("SET FOREIGN_KEY_CHECKS = 0;"))
            conn.execute(text(f"DELETE FROM {table_name}"))
            conn.execute(text("SET FOREIGN_KEY_CHECKS = 1;"))
            conn.commit()
            
            print(f"Writing data to Remote.{table_name}...")
            df.to_sql(table_name, remote_engine, if_exists='append', index=False)
            print("Sync complete.")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        sync_table(sys.argv[1])
    else:
        print("Please provide a table name as an argument.")
