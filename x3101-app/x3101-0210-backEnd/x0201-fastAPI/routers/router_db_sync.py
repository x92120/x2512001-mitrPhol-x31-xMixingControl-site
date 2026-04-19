"""
Database Sync Router
====================
Provides endpoints to sync data between Remote DB and Cloud DB (backup only).

Endpoints:
  POST /db-sync/remote-to-cloud  → Sync Remote DB → Cloud DB (backup)
  GET  /db-sync/status           → Get connection status
  GET  /db-sync/active-db        → Get the currently active database
"""

import pymysql
import re
import logging
import os
from fastapi import APIRouter, HTTPException
from database import get_active_db_info

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/db-sync", tags=["Database Sync"])

# Database configs
DB_USER = os.getenv("DB_USER", "mixingcontrol")
DB_PASSWORD = os.getenv("DB_PASSWORD", "admin100")
DB_PORT = int(os.getenv("DB_PORT", "3306"))
DB_NAME = os.getenv("DB_NAME", "xMixingControl")
CLOUD_HOST = os.getenv("CLOUD_DB", "152.42.166.150")
REMOTE_HOST = os.getenv("REMOTE_DB", "192.168.121.11")


def get_db_config(host: str) -> dict:
    return {
        'host': host,
        'port': DB_PORT,
        'user': DB_USER,
        'password': DB_PASSWORD,
        'database': DB_NAME,
        'charset': 'utf8mb4',
        'connect_timeout': 10,
    }


def sync_database(source_host: str, target_host: str, source_label: str, target_label: str) -> dict:
    """Sync all tables and views from source DB to target DB."""
    log = []
    tables_synced = 0
    views_synced = 0
    total_rows = 0

    try:
        log.append(f"Connecting to {source_label} ({source_host})...")
        source_conn = pymysql.connect(**get_db_config(source_host), cursorclass=pymysql.cursors.DictCursor)
        log.append(f"✓ Connected to {source_label}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Cannot connect to {source_label}: {str(e)}")

    try:
        log.append(f"Connecting to {target_label} ({target_host})...")
        target_conn = pymysql.connect(**get_db_config(target_host), cursorclass=pymysql.cursors.DictCursor)
        log.append(f"✓ Connected to {target_label}")
    except Exception as e:
        source_conn.close()
        raise HTTPException(status_code=500, detail=f"Cannot connect to {target_label}: {str(e)}")

    source_cur = source_conn.cursor()
    target_cur = target_conn.cursor()

    try:
        # Disable FK checks
        target_cur.execute("SET FOREIGN_KEY_CHECKS = 0")
        target_cur.execute("SET SQL_MODE = 'NO_AUTO_VALUE_ON_ZERO'")

        # Get tables
        source_cur.execute(f"SHOW FULL TABLES WHERE Table_type = 'BASE TABLE'")
        tables = [row[f'Tables_in_{DB_NAME}'] for row in source_cur.fetchall()]
        log.append(f"Found {len(tables)} tables")

        # Sync tables
        for table in tables:
            try:
                source_cur.execute(f"SHOW CREATE TABLE `{table}`")
                create_sql = source_cur.fetchone()['Create Table']

                target_cur.execute(f"DROP TABLE IF EXISTS `{table}`")
                target_cur.execute(create_sql)

                source_cur.execute(f"SELECT * FROM `{table}`")
                rows = source_cur.fetchall()

                if rows:
                    columns = list(rows[0].keys())
                    cols_str = ', '.join([f'`{c}`' for c in columns])
                    placeholders = ', '.join(['%s'] * len(columns))
                    insert_sql = f"INSERT INTO `{table}` ({cols_str}) VALUES ({placeholders})"

                    batch_size = 500
                    for j in range(0, len(rows), batch_size):
                        batch = rows[j:j + batch_size]
                        values = [tuple(row[c] for c in columns) for row in batch]
                        target_cur.executemany(insert_sql, values)

                    target_conn.commit()

                tables_synced += 1
                total_rows += len(rows)
                log.append(f"✓ {table}: {len(rows)} rows")
            except Exception as e:
                log.append(f"✗ {table}: {str(e)}")
                target_conn.rollback()

        # Sync views
        source_cur.execute(f"SHOW FULL TABLES WHERE Table_type = 'VIEW'")
        views = [row[f'Tables_in_{DB_NAME}'] for row in source_cur.fetchall()]

        for view in views:
            try:
                source_cur.execute(f"SHOW CREATE VIEW `{view}`")
                create_view = source_cur.fetchone()['Create View']
                target_cur.execute(f"DROP VIEW IF EXISTS `{view}`")
                create_view = re.sub(r'DEFINER=`[^`]+`@`[^`]+`\s*', '', create_view)
                target_cur.execute(create_view)
                target_conn.commit()
                views_synced += 1
                log.append(f"✓ View: {view}")
            except Exception as e:
                log.append(f"✗ View {view}: {str(e)}")
                target_conn.rollback()

        # Re-enable FK checks
        target_cur.execute("SET FOREIGN_KEY_CHECKS = 1")
        target_conn.commit()

    finally:
        source_cur.close()
        target_cur.close()
        source_conn.close()
        target_conn.close()

    return {
        "status": "ok",
        "direction": f"{source_label} → {target_label}",
        "tables_synced": tables_synced,
        "views_synced": views_synced,
        "total_rows": total_rows,
        "log": log,
    }


# =============================================================================
# ACTIVE DATABASE ENDPOINT
# =============================================================================

@router.get("/active-db")
def get_active_db():
    """Get the currently active database configuration."""
    return get_active_db_info()


@router.get("/db-options")
def get_db_options():
    """List available database option (Remote DB only)."""
    active = get_active_db_info()
    return [active]


# =============================================================================
# SYNC STATUS & ACTIONS
# =============================================================================

@router.get("/status")
def get_sync_status():
    """Check connection status of the Remote database."""
    result = {
        "remote": {"host": REMOTE_HOST, "status": "unknown", "tables": 0},
    }
    try:
        conn = pymysql.connect(**get_db_config(REMOTE_HOST))
        cur = conn.cursor()
        cur.execute("SHOW TABLES")
        result["remote"]["tables"] = len(cur.fetchall())
        result["remote"]["status"] = "connected"
        cur.close()
        conn.close()
    except Exception as e:
        result["remote"]["status"] = f"error: {str(e)}"
    return result


@router.post("/remote-to-cloud")
def sync_remote_to_cloud():
    """Sync all data from Remote DB to Cloud DB (backup)."""
    logger.info("Starting sync: Remote → Cloud")
    return sync_database(REMOTE_HOST, CLOUD_HOST, "Remote", "Cloud")
