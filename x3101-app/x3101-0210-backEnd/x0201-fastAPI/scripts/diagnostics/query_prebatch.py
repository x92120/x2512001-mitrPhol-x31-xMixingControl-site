from database import SessionLocal
from sqlalchemy import text

db = SessionLocal()
# Let's search the tables for this prebatch_id
query = text("""
    SELECT * 
    FROM prebatch_recs 
    WHERE prebatch_id LIKE '%P260321-02-02-001FV020CREC%'
       OR prebatch_id LIKE '%FV020C%' LIMIT 5;
""")
result = db.execute(query).fetchall()

print("Found records:")
for row in result:
    print(dict(row._mapping))

db.close()
