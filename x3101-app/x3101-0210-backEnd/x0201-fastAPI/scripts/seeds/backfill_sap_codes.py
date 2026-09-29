from sqlalchemy import text
from database import engine

def backfill():
    with engine.connect() as conn:
        print("Backfilling mat_sap_code in prebatch_recs...")
        try:
            # SQL to update prebatch_recs from ingredients table
            query = text("""
                UPDATE prebatch_recs p
                JOIN ingredients i ON p.re_code = i.re_code
                SET p.mat_sap_code = i.mat_sap_code
                WHERE p.mat_sap_code IS NULL OR p.mat_sap_code = ''
            """)
            result = conn.execute(query)
            conn.commit()
            print(f"Successfully updated {result.rowcount} records.")
            
            # Also check if we should update prebatch_reqs if it exists there (it doesn't seem to have the column based on models.py)
            
        except Exception as e:
            print(f"Error during backfill: {e}")

if __name__ == "__main__":
    backfill()
