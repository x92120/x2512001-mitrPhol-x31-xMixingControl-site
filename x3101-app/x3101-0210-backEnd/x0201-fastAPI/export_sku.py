import pandas as pd
from database import SessionLocal
from sqlalchemy import text
import os

def main():
    db = SessionLocal()
    # Using v_sku_complete to get all detailed information nicely flattened
    query = text("""
        SELECT 
            sku_id as "SKU ID",
            sku_name as "SKU Name",
            std_batch_size as "Standard Batch Size",
            uom as "UOM",
            phase_number as "Phase",
            sub_step as "Step",
            action as "Action (Legacy)",
            action_code as "Action Code",
            action_description as "Action Description",
            re_code as "RE Code",
            ingredient_name as "Ingredient Name",
            mat_sap_code as "SAP Code",
            required_amount as "Require",
            destination as "Destination",
            temperature as "Temperature",
            step_time as "Time",
            agitator_rpm as "Agitator RPM",
            high_shear_rpm as "High Shear RPM",
            setup_step as "Setup Step",
            status as "Status"
        FROM v_sku_complete
        ORDER BY sku_id, CAST(phase_number AS INTEGER), sub_step
        ;
    """)
    
    try:
        # We can read_sql directly using pandas
        engine = db.get_bind()
        df = pd.read_sql_query(query, engine)
        
        output_file = r"e:\x01-git\x2512001-MitrPhol\x23\All_SKU_Export.xlsx"
        
        # Write to excel
        df.to_excel(output_file, index=False)
        print(f"SUCCESS: Exported {len(df)} rows to {output_file}")
    except Exception as e:
        print(f"Error executing pandas export: {e}")
        # fallback to CSV if openpyxl fails, just in case
        output_csv = r"e:\x01-git\x2512001-MitrPhol\x23\All_SKU_Export.csv"
        try:
            df.to_csv(output_csv, index=False)
            print(f"Fallback SUCCESS: Exported to CSV instead at {output_csv}")
        except Exception as csv_e:
            print(f"Failed fallback CSV: {csv_e}")
    finally:
        db.close()

if __name__ == "__main__":
    main()
