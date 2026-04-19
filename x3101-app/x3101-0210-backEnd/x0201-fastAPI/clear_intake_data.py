from sqlalchemy import create_engine, text
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

DB_USER = os.getenv("DB_USER", "mixingcontrol")
DB_PASSWORD = os.getenv("DB_PASSWORD", "admin100")
DB_HOST = os.getenv("DB_HOST", "192.168.121.11")
DB_PORT = os.getenv("DB_PORT", "3306")
DB_NAME = os.getenv("DB_NAME", "xMixingControl")

SQLALCHEMY_DATABASE_URL = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
engine = create_engine(SQLALCHEMY_DATABASE_URL)

def clear_intake_data():
    tables = [
        "intake_package_receive",
        "ingredient_intake_history",
        "ingredient_intake_lists"
    ]
    
    with engine.connect() as connection:
        # Disable foreign key checks to allow truncating/deleting
        connection.execute(text("SET FOREIGN_KEY_CHECKS = 0;"))
        
        for table in tables:
            print(f"Clearing table: {table}")
            connection.execute(text(f"DELETE FROM {table};"))
            # Optionally reset auto-increment
            connection.execute(text(f"ALTER TABLE {table} AUTO_INCREMENT = 1;"))
            
        connection.execute(text("SET FOREIGN_KEY_CHECKS = 1;"))
        connection.commit()
        print("All intake data cleared successfully.")

if __name__ == "__main__":
    clear_intake_data()
