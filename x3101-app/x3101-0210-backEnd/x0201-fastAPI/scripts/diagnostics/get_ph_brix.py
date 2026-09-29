from database import SessionLocal
from sqlalchemy import text

def main():
    db = SessionLocal()
    query = text("SELECT phase_number, sub_step, ph, brix, ph_sp, brix_sp FROM sku_steps WHERE sku_id = 'SFCFRU4200' ORDER BY phase_number, sub_step")
    rows = db.execute(query).fetchall()
    for r in rows:
        print(f"Phase {r[0]} Step {r[1]}: ph={r[2]}, brix={r[3]}, ph_sp={r[4]}, brix_sp={r[5]}")
    db.close()

if __name__ == "__main__":
    main()
