from sqlalchemy import text
from database import engine

def update_schema():
    with engine.connect() as conn:
        print("Checking for prebatch_id in prebatch_recs...")
        try:
            # Check if column exists
            result = conn.execute(text("SHOW COLUMNS FROM prebatch_recs LIKE 'prebatch_id'"))
            if result.fetchone():
                print("Column 'prebatch_id' already exists.")
            else:
                print("Adding column 'prebatch_id' to prebatch_recs...")
                conn.execute(text("ALTER TABLE prebatch_recs ADD COLUMN prebatch_id VARCHAR(100) AFTER intake_lot_id"))
                conn.execute(text("CREATE INDEX ix_prebatch_recs_prebatch_id ON prebatch_recs (prebatch_id)"))
                conn.commit()
                print("Successfully added column prebatch_id.")

            # Check for recode_batch_id in prebatch_recs
            result = conn.execute(text("SHOW COLUMNS FROM prebatch_recs LIKE 'recode_batch_id'"))
            if result.fetchone():
                print("Column 'recode_batch_id' already exists.")
            else:
                print("Adding column 'recode_batch_id' to prebatch_recs...")
                conn.execute(text("ALTER TABLE prebatch_recs ADD COLUMN recode_batch_id VARCHAR(50) AFTER prebatch_id"))
                conn.execute(text("CREATE INDEX ix_prebatch_recs_recode_batch_id ON prebatch_recs (recode_batch_id)"))
                conn.commit()
                print("Successfully added column recode_batch_id.")

            # Check for mat_sap_code in prebatch_recs
            result = conn.execute(text("SHOW COLUMNS FROM prebatch_recs LIKE 'mat_sap_code'"))
            if result.fetchone():
                print("Column 'mat_sap_code' already exists.")
            else:
                print("Adding column 'mat_sap_code' to prebatch_recs...")
                conn.execute(text("ALTER TABLE prebatch_recs ADD COLUMN mat_sap_code VARCHAR(50) AFTER intake_lot_id"))
                conn.execute(text("CREATE INDEX ix_prebatch_recs_mat_sap_code ON prebatch_recs (mat_sap_code)"))
                conn.commit()
                print("Successfully added column mat_sap_code.")
        except Exception as e:
            print(f"Error updating schema: {e}")

if __name__ == "__main__":
    update_schema()
