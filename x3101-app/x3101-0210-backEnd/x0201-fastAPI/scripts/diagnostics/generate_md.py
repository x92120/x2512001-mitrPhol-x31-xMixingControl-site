from database import SessionLocal
from sqlalchemy import text
import os

def main():
    db = SessionLocal()
    
    md_content = "# Detailed Report: SKUs Updated to Action Code 21010\n\n"
    md_content += "This document lists all specific entries that were migrated to the new `21010` (Manual Add to Mixing Tank) action code.\n\n"
    
    try:
        # We query the exact columns that exist in the DB
        query_sku = text("SELECT id, sku_id, master_step, sub_step FROM sku_steps WHERE action_code = '21010' ORDER BY sku_id, master_step, sub_step")
        result_sku = db.execute(query_sku)
        
        rows = result_sku.fetchall()
        
        md_content += f"## `sku_steps` table ({len(rows)} rows)\n\n"
        md_content += "| ID | SKU ID | Master Step | Sub Step |\n"
        md_content += "| :--- | :--- | :--- | :--- |\n"
        
        for r in rows:
            md_content += f"| {r[0]} | {r[1]} | {r[2]} | {r[3]} |\n"
            
    except Exception as e:
        md_content += f"Error reading sku_steps: {e}\n"

    # For mixing batch step log, let's just get whatever columns it has dynamically to avoid hardcoded column errors
    try:
        query_batch = text("SELECT * FROM mixing_batch_step_log WHERE action_code = '21010'")
        result_batch = db.execute(query_batch)
        keys = list(result_batch.keys())
        
        # Grab first 4 columns dynamically
        id_cols_indices = [i for i, key in enumerate(keys)][:4]
        
        rows = result_batch.fetchall()
        
        md_content += f"\n## `mixing_batch_step_log` table ({len(rows)} rows)\n\n"
        header = "| " + " | ".join([keys[i] for i in id_cols_indices]) + " |\n"
        separator = "| " + " | ".join([":---" for _ in id_cols_indices]) + " |\n"
        md_content += header + separator
        
        for r in rows:
            row_tuple = tuple(r)
            md_content += "| " + " | ".join([str(row_tuple[i]) for i in id_cols_indices]) + " |\n"
            
    except Exception as e:
        md_content += f"\nError reading mixing_batch_step_log: {e}\n"
        
    artifact_path = '/Users/x92120/xGit/x2512001-mitrPhol-x31-xMixingControl-site/sku_updates_21010.md'
    
    with open(artifact_path, 'w') as f:
        f.write(md_content)
        
    db.close()

if __name__ == "__main__":
    main()
