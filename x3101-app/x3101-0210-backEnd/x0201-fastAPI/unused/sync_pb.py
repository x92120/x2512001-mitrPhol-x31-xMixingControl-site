import models
from database import engine
from sqlalchemy import text

print("Dropping old prebatch tables if exists...")
try:
    with engine.connect() as conn:
        conn.execute(text("DROP TABLE IF EXISTS prebatch_recs"))
        conn.execute(text("DROP TABLE IF EXISTS prebatch_reqs"))
        conn.execute(text("DROP TABLE IF EXISTS pb_logs"))
        conn.execute(text("DROP TABLE IF EXISTS pb_tasks"))
        conn.execute(text("DROP TABLE IF EXISTS prebatch_records"))
        conn.execute(text("DROP TABLE IF EXISTS prebatch_requires"))
        conn.commit()
    print("Dropped.")
except Exception as e:
    print(f"Error dropping: {e}")

print("Creating all tables (prebatch_reqs, prebatch_recs)...")
models.Base.metadata.create_all(bind=engine)
print("Done.")
