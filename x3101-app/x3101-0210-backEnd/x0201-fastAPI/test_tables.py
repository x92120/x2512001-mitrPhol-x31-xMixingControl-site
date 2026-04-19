from database import SessionLocal
from sqlalchemy import text

db = SessionLocal()
query = text("""
SELECT table_name 
FROM information_schema.tables 
WHERE table_schema = 'public' 
AND (table_name LIKE '%action%' OR table_name LIKE '%sku%');
""")
result = db.execute(query).fetchall()

print("Matching Tables:", [row[0] for row in result])
db.close()
