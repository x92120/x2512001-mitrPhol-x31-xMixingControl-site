from database import SessionLocal
from sqlalchemy import text

db = SessionLocal()
query = text("""
UPDATE sku_actions
SET action_description = 'Manual Add to Mixing Tank'
WHERE action_code = '30010';
""")
db.execute(query)
db.commit()

# Verify
verify = text("SELECT action_code, action_description FROM sku_actions WHERE action_code = '30010';")
result = db.execute(verify).fetchone()
print(f"Updated Action: {result[0]} -> {result[1]}" if result else "Action Code not found.")

db.close()
