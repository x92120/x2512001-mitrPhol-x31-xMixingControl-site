from database import SessionLocal
from sqlalchemy import text

db = SessionLocal()
query = text("SELECT * FROM sku_steps LIMIT 5;")
result = db.execute(query).fetchall()

print("Columns:", [k for k in dict(result[0]._mapping).keys()] if result else "No data")

print("\nRows:")
for row in result:
    print(dict(row._mapping))

db.close()
