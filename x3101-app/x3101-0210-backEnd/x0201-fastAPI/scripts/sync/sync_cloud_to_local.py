#!/usr/bin/env python3
"""
Sync database from Cloud DB to Local DB using pymysql.
Copies all table structures (CREATE TABLE) and data.
Also syncs views.
"""
import pymysql
import sys

# Database config
CLOUD = {
    'host': '152.42.166.150',
    'port': 3306,
    'user': 'mixingcontrol',
    'password': 'admin100',
    'database': 'xMixingControl',
    'charset': 'utf8mb4',
}

LOCAL = {
    'host': '192.168.121.11',
    'port': 3306,
    'user': 'mixingcontrol',
    'password': 'admin100',
    'database': 'xMixingControl',
    'charset': 'utf8mb4',
}

def get_connection(config):
    return pymysql.connect(**config, cursorclass=pymysql.cursors.DictCursor)

def sync():
    print("=" * 60)
    print("  Cloud -> Local DB Sync")
    print("=" * 60)
    
    # Connect to both databases
    print(f"\n[1] Connecting to Cloud DB ({CLOUD['host']})...")
    cloud_conn = get_connection(CLOUD)
    print(f"    ✓ Connected to Cloud DB")
    
    print(f"[2] Connecting to Local DB ({LOCAL['host']})...")
    local_conn = get_connection(LOCAL)
    print(f"    ✓ Connected to Local DB")
    
    cloud_cur = cloud_conn.cursor()
    local_cur = local_conn.cursor()
    
    # Disable FK checks on local
    local_cur.execute("SET FOREIGN_KEY_CHECKS = 0")
    local_cur.execute("SET SQL_MODE = 'NO_AUTO_VALUE_ON_ZERO'")
    
    # Get all tables from cloud
    print(f"\n[3] Fetching table list from Cloud...")
    cloud_cur.execute("SHOW FULL TABLES WHERE Table_type = 'BASE TABLE'")
    tables = [row[f'Tables_in_{CLOUD["database"]}'] for row in cloud_cur.fetchall()]
    print(f"    Found {len(tables)} tables")
    
    # Sync each table
    print(f"\n[4] Syncing tables...")
    for i, table in enumerate(tables, 1):
        try:
            # Get CREATE TABLE from cloud
            cloud_cur.execute(f"SHOW CREATE TABLE `{table}`")
            create_sql = cloud_cur.fetchone()['Create Table']
            
            # Drop and recreate on local
            local_cur.execute(f"DROP TABLE IF EXISTS `{table}`")
            local_cur.execute(create_sql)
            
            # Get all data from cloud
            cloud_cur.execute(f"SELECT * FROM `{table}`")
            rows = cloud_cur.fetchall()
            
            if rows:
                # Build INSERT statement
                columns = list(rows[0].keys())
                cols_str = ', '.join([f'`{c}`' for c in columns])
                placeholders = ', '.join(['%s'] * len(columns))
                insert_sql = f"INSERT INTO `{table}` ({cols_str}) VALUES ({placeholders})"
                
                # Insert in batches
                batch_size = 500
                for j in range(0, len(rows), batch_size):
                    batch = rows[j:j+batch_size]
                    values = [tuple(row[c] for c in columns) for row in batch]
                    local_cur.executemany(insert_sql, values)
                
                local_conn.commit()
            
            print(f"    [{i}/{len(tables)}] ✓ {table}: {len(rows)} rows")
        except Exception as e:
            print(f"    [{i}/{len(tables)}] ✗ {table}: {e}")
            local_conn.rollback()
    
    # Sync views
    print(f"\n[5] Syncing views...")
    cloud_cur.execute("SHOW FULL TABLES WHERE Table_type = 'VIEW'")
    views = [row[f'Tables_in_{CLOUD["database"]}'] for row in cloud_cur.fetchall()]
    print(f"    Found {len(views)} views")
    
    for i, view in enumerate(views, 1):
        try:
            cloud_cur.execute(f"SHOW CREATE VIEW `{view}`")
            create_view = cloud_cur.fetchone()['Create View']
            
            local_cur.execute(f"DROP VIEW IF EXISTS `{view}`")
            # Remove DEFINER clause to avoid permission issues
            import re
            create_view = re.sub(r'DEFINER=`[^`]+`@`[^`]+`\s*', '', create_view)
            local_cur.execute(create_view)
            local_conn.commit()
            print(f"    [{i}/{len(views)}] ✓ {view}")
        except Exception as e:
            print(f"    [{i}/{len(views)}] ✗ {view}: {e}")
            local_conn.rollback()
    
    # Re-enable FK checks
    local_cur.execute("SET FOREIGN_KEY_CHECKS = 1")
    local_conn.commit()
    
    # Close connections
    cloud_cur.close()
    local_cur.close()
    cloud_conn.close()
    local_conn.close()
    
    print(f"\n{'=' * 60}")
    print(f"  Sync complete! {len(tables)} tables + {len(views)} views")
    print(f"{'=' * 60}")

if __name__ == '__main__':
    try:
        sync()
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)
