"""
Migration: Create sku_groups table and update sku_masters.
Run this on the server: python3 migrate_sku_group.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from database import engine
from sqlalchemy import text

with engine.connect() as conn:
    # 1. Create sku_groups table
    try:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS sku_groups (
                id INT AUTO_INCREMENT PRIMARY KEY,
                group_code VARCHAR(50) NOT NULL UNIQUE,
                group_name VARCHAR(100) NOT NULL,
                description VARCHAR(255),
                status VARCHAR(20) DEFAULT 'Active',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                INDEX idx_group_code (group_code)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """))
        conn.commit()
        print("✅ Table sku_groups created")
    except Exception as e:
        print(f"⚠️ Table may exist: {e}")

    # 2. Add sku_group column to sku_masters if not exists
    try:
        conn.execute(text("ALTER TABLE sku_masters ADD COLUMN sku_group VARCHAR(50) DEFAULT NULL"))
        conn.commit()
        print("✅ Column sku_group added to sku_masters")
    except Exception as e:
        print(f"⚠️ Column may exist: {e}")

    # 3. Add FK constraint (ignore if exists)
    try:
        conn.execute(text("""
            ALTER TABLE sku_masters 
            ADD CONSTRAINT fk_sku_group 
            FOREIGN KEY (sku_group) REFERENCES sku_groups(group_code)
            ON UPDATE CASCADE ON DELETE SET NULL
        """))
        conn.commit()
        print("✅ FK constraint added")
    except Exception as e:
        print(f"⚠️ FK may exist: {e}")

    # 4. Update view
    conn.execute(text("""
        CREATE OR REPLACE VIEW v_sku_master_detail AS
        SELECT 
            sm.id, sm.sku_id, sm.sku_name, sm.std_batch_size, sm.uom, sm.status,
            sm.creat_by, sm.created_at, sm.update_by, sm.updated_at,
            sm.sku_group,
            sg.group_name AS sku_group_name,
            COUNT(DISTINCT ss.phase_number) AS total_phases,
            COUNT(ss.id) AS total_sub_steps,
            MAX(ss.updated_at) AS last_step_update
        FROM sku_masters sm
        LEFT JOIN sku_groups sg ON sm.sku_group = sg.group_code
        LEFT JOIN sku_steps ss ON sm.sku_id = ss.sku_id
        GROUP BY sm.id, sm.sku_id, sm.sku_name, sm.std_batch_size, sm.uom, sm.status,
                 sm.creat_by, sm.created_at, sm.update_by, sm.updated_at, sm.sku_group,
                 sg.group_name
    """))
    conn.commit()
    print("✅ View v_sku_master_detail updated with sku_group + group_name")

    # 5. Seed some default groups
    try:
        conn.execute(text("""
            INSERT IGNORE INTO sku_groups (group_code, group_name, description) VALUES
            ('SYR', 'Syrup', 'Syrup products'),
            ('BEV', 'Beverage', 'Beverage products'),
            ('COF', 'Coffee', 'Coffee-based products'),
            ('FLV', 'Flavour', 'Flavour concentrates')
        """))
        conn.commit()
        print("✅ Default groups seeded")
    except Exception as e:
        print(f"⚠️ Seed: {e}")

print("🎉 Migration complete!")
