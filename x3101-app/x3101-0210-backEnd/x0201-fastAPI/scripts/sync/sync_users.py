import os
import pandas as pd
import json
import numpy as np
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

DB_USER = os.getenv("DB_USER", "mixingcontrol")
DB_PASSWORD = os.getenv("DB_PASSWORD", "admin100")
DB_PORT = os.getenv("DB_PORT", "3306")
DB_NAME = os.getenv("DB_NAME", "xMixingControl")

CLOUD_HOST = "152.42.166.150"
REMOTE_HOST = "192.168.121.11"

def clean_val(val):
    if pd.isna(val) or val is np.nan:
        return None
    return val

def sync_users():
    cloud_url = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{CLOUD_HOST}:{DB_PORT}/{DB_NAME}"
    remote_url = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{REMOTE_HOST}:{DB_PORT}/{DB_NAME}"
    
    cloud_engine = create_engine(cloud_url)
    remote_engine = create_engine(remote_url)
    
    try:
        print("Fetching users from Cloud...")
        df = pd.read_sql_table('users', cloud_engine)
        print(f"Found {len(df)} users.")
        
        with remote_engine.connect() as conn:
            print("Clearing Remote users...")
            conn.execute(text("SET FOREIGN_KEY_CHECKS = 0;"))
            conn.execute(text("DELETE FROM users"))
            conn.commit()
            
            print("Writing users to Remote...")
            for _, row in df.iterrows():
                # Convert permissions to JSON string if it's not already
                permissions_val = row['permissions']
                if not isinstance(permissions_val, str) and permissions_val is not None:
                    permissions_val = json.dumps(permissions_val)
                elif permissions_val is None:
                    permissions_val = "[]"
                
                # Convert timestamps to strings or None
                last_login = row['last_login'].strftime('%Y-%m-%d %H:%M:%S') if pd.notnull(row['last_login']) else None
                created_at = row['created_at'].strftime('%Y-%m-%d %H:%M:%S') if pd.notnull(row['created_at']) else None
                updated_at = row['updated_at'].strftime('%Y-%m-%d %H:%M:%S') if pd.notnull(row['updated_at']) else None

                conn.execute(text("""
                    INSERT INTO users (id, username, email, password_hash, full_name, role, department, status, permissions, last_login, created_at, updated_at) 
                    VALUES (:id, :username, :email, :password_hash, :full_name, :role, :department, :status, :permissions, :last_login, :created_at, :updated_at)
                """), {
                    "id": clean_val(row['id']),
                    "username": clean_val(row['username']),
                    "email": clean_val(row['email']),
                    "password_hash": clean_val(row['password_hash']),
                    "full_name": clean_val(row['full_name']),
                    "role": clean_val(row['role']),
                    "department": clean_val(row['department']),
                    "status": clean_val(row['status']),
                    "permissions": permissions_val,
                    "last_login": last_login,
                    "created_at": created_at,
                    "updated_at": updated_at
                })
            
            conn.execute(text("SET FOREIGN_KEY_CHECKS = 1;"))
            conn.commit()
            print("User sync successful.")
            
            # Verify
            res = conn.execute(text("SELECT COUNT(*) FROM users"))
            count = res.scalar()
            print(f"Verification: {count} users now in Remote DB.")
            
    except Exception as e:
        print(f"User sync failed: {e}")

if __name__ == "__main__":
    sync_users()
