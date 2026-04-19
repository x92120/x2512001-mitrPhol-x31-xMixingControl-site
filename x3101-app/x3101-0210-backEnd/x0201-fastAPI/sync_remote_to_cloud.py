#!/usr/bin/env python3
"""
Sync database from Remote DB to Cloud DB using pymysql.
Copies all table structures (CREATE TABLE) and data.
Also syncs views.
Direction: Remote (192.168.121.11) -> Cloud (152.42.166.150)
"""
import pymysql
import re
import sys

# Database config
REMOTE = {
    'host': '192.168.121.11',
    'port': 3306,
    'user': 'mixingcontrol',
    'password': 'admin100',
    'database': 'xMixingControl',
    'charset': 'utf8mb4',
}

CLOUD = {
    'host': '152.42.166.150',
    'port': 3306,
    'user': 'mixingcontrol',
    'password': 'admin100',
    'database': 'xMixingControl',
    'charset': 'utf8mb4',
    'connect_timeout': 30,
    'read_timeout': 120,
    'write_timeout': 120,
}

def get_connection(config):
    return pymysql.connect(**config, cursorclass=pymysql.cursors.DictCursor)

def sync():
    print("=" * 60)
    print("  Remote -> Cloud DB Sync")
    print("=" * 60)

    # Connect to both databases
    print(f"\n[1] Connecting to Remote DB ({REMOTE['host']})...")
    remote_conn = get_connection(REMOTE)
    print(f"    ✓ Connected to Remote DB")

    print(f"[2] Connecting to Cloud DB ({CLOUD['host']})...")
    cloud_conn = get_connection(CLOUD)
    print(f"    ✓ Connected to Cloud DB")

    remote_cur = remote_conn.cursor()
    cloud_cur = cloud_conn.cursor()

    # Disable FK checks on cloud
    cloud_cur.execute("SET FOREIGN_KEY_CHECKS = 0")
    cloud_cur.execute("SET SQL_MODE = 'NO_AUTO_VALUE_ON_ZERO'")

    # Get all tables from remote
    print(f"\n[3] Fetching table list from Remote...")
    remote_cur.execute("SHOW FULL TABLES WHERE Table_type = 'BASE TABLE'")
    tables = [row[f'Tables_in_{REMOTE["database"]}'] for row in remote_cur.fetchall()]
    print(f"    Found {len(tables)} tables")

    # Sync each table
    print(f"\n[4] Syncing tables...")
    for i, table in enumerate(tables, 1):
        try:
            # Get CREATE TABLE from remote
            remote_cur.execute(f"SHOW CREATE TABLE `{table}`")
            create_sql = remote_cur.fetchone()['Create Table']

            # Drop and recreate on cloud
            cloud_cur.execute(f"DROP TABLE IF EXISTS `{table}`")
            cloud_cur.execute(create_sql)

            # Get all data from remote
            remote_cur.execute(f"SELECT * FROM `{table}`")
            rows = remote_cur.fetchall()

            if rows:
                # Build INSERT statement
                columns = list(rows[0].keys())
                cols_str = ', '.join([f'`{c}`' for c in columns])
                placeholders = ', '.join(['%s'] * len(columns))
                insert_sql = f"INSERT INTO `{table}` ({cols_str}) VALUES ({placeholders})"

                # Insert in batches (smaller batch for cloud to avoid timeouts)
                batch_size = 200
                for j in range(0, len(rows), batch_size):
                    batch = rows[j:j+batch_size]
                    values = [tuple(row[c] for c in columns) for row in batch]
                    cloud_cur.executemany(insert_sql, values)

                cloud_conn.commit()

            print(f"    [{i}/{len(tables)}] ✓ {table}: {len(rows)} rows")
        except Exception as e:
            print(f"    [{i}/{len(tables)}] ✗ {table}: {e}")
            cloud_conn.rollback()

    # Sync views
    print(f"\n[5] Syncing views...")
    remote_cur.execute("SHOW FULL TABLES WHERE Table_type = 'VIEW'")
    views = [row[f'Tables_in_{REMOTE["database"]}'] for row in remote_cur.fetchall()]
    print(f"    Found {len(views)} views")

    for i, view in enumerate(views, 1):
        try:
            remote_cur.execute(f"SHOW CREATE VIEW `{view}`")
            create_view = remote_cur.fetchone()['Create View']

            cloud_cur.execute(f"DROP VIEW IF EXISTS `{view}`")
            # Remove DEFINER clause to avoid permission issues
            create_view = re.sub(r'DEFINER=`[^`]+`@`[^`]+`\s*', '', create_view)
            cloud_cur.execute(create_view)
            cloud_conn.commit()
            print(f"    [{i}/{len(views)}] ✓ {view}")
        except Exception as e:
            print(f"    [{i}/{len(views)}] ✗ {view}: {e}")
            cloud_conn.rollback()

    # Re-enable FK checks
    cloud_cur.execute("SET FOREIGN_KEY_CHECKS = 1")
    cloud_conn.commit()

    # Close connections
    remote_cur.close()
    cloud_cur.close()
    remote_conn.close()
    cloud_conn.close()

    print(f"\n{'=' * 60}")
    print(f"  Sync complete! {len(tables)} tables + {len(views)} views")
    print(f"{'=' * 60}")

if __name__ == '__main__':
    try:
        sync()
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)
