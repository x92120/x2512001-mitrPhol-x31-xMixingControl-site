import sys, os
from sqlalchemy import inspect, text
sys.path.insert(0, os.path.dirname(__file__))
from database import engine

def check_structure():
    inspector = inspect(engine)
    columns = inspector.get_columns('sku_steps')
    for column in columns:
        print(f"Column: {column['name']}, Type: {column['type']}, Nullable: {column['nullable']}")

if __name__ == "__main__":
    check_structure()
