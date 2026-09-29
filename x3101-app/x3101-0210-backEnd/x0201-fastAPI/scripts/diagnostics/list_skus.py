import pandas as pd
from database import SessionLocal
from sqlalchemy import text

def main():
    db = SessionLocal()
    
    query = text("""
        SELECT 
            sku_id,
            sku_name,
            phase_number,
            sub_step,
            action_description,
            ingredient_name,
            required_amount,
            destination
        FROM v_sku_complete
        ORDER BY sku_id, CAST(phase_number AS UNSIGNED), sub_step
    """)
    
    engine = db.get_bind()
    df = pd.read_sql_query(query, engine)
    db.close()
    
    md = "# 🏭 SKU Recipes: Process & Steps\n\n"
    
    current_sku = None
    current_phase = None
    
    for _, row in df.iterrows():
        sku = f"{row['sku_id']} - {row['sku_name']}"
        phase = row['phase_number']
        
        if sku != current_sku:
            md += f"\n## 📦 SKU: {sku}\n"
            current_sku = sku
            current_phase = None
            
        if phase != current_phase:
            md += f"\n### 🔄 Process Phase: {phase}\n"
            md += "| Step | Action | Ingredient | Target | Destination |\n"
            md += "|---|---|---|---|---|\n"
            current_phase = phase
            
        step = row['sub_step']
        action = row['action_description'] or "-"
        ing = row['ingredient_name'] or "-"
        amt = f"{row['required_amount']} kg" if pd.notnull(row['required_amount']) else "-"
        dest = row['destination'] or "-"
        
        md += f"| {step} | {action} | {ing} | {amt} | {dest} |\n"
        
    with open('sku_recipes.md', 'w', encoding='utf-8') as f:
        f.write(md)
        
    print("Generated sku_recipes.md")

if __name__ == '__main__':
    main()
