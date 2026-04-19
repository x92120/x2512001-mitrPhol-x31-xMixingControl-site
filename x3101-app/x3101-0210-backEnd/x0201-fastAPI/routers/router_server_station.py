"""
Server Station Router
=====================
Monitors a remote server (192.168.121.11) via MySQL statistics and network checks.

Endpoints:
  GET /server-station/status      → Full status (ping, MySQL stats, DB sizes)
  GET /server-station/ping        → Quick ping check
"""

import pymysql
import subprocess
import os
import logging
import time
from fastapi import APIRouter

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/server-station", tags=["Server Station"])

# Remote server config
STATION_HOST = os.getenv("STATION_HOST", "192.168.121.11")
DB_USER = os.getenv("DB_USER", "mixingcontrol")
DB_PASSWORD = os.getenv("DB_PASSWORD", "admin100")
DB_PORT = int(os.getenv("DB_PORT", "3306"))
DB_NAME = os.getenv("DB_NAME", "xMixingControl")


def ping_host(host: str, count: int = 3) -> dict:
    """Ping a host and return latency stats."""
    try:
        result = subprocess.run(
            ['ping', '-c', str(count), '-W', '2', host],
            capture_output=True, text=True, timeout=10
        )
        lines = result.stdout.strip().split('\n')

        # Parse packet loss
        packet_line = [l for l in lines if 'packet loss' in l]
        loss = '100%'
        if packet_line:
            import re
            m = re.search(r'(\d+)% packet loss', packet_line[0])
            if m:
                loss = f"{m.group(1)}%"

        # Parse latency
        latency = None
        rtt_line = [l for l in lines if 'rtt' in l or 'round-trip' in l]
        if rtt_line:
            import re
            m = re.search(r'= ([\d.]+)/([\d.]+)/([\d.]+)', rtt_line[0])
            if m:
                latency = {
                    'min': float(m.group(1)),
                    'avg': float(m.group(2)),
                    'max': float(m.group(3)),
                }

        return {
            'reachable': result.returncode == 0,
            'packet_loss': loss,
            'latency': latency,
        }
    except Exception as e:
        return {'reachable': False, 'packet_loss': '100%', 'latency': None, 'error': str(e)}


def get_mysql_stats(host: str) -> dict:
    """Get MySQL server stats from a remote host."""
    try:
        start = time.time()
        conn = pymysql.connect(
            host=host, port=DB_PORT, user=DB_USER,
            password=DB_PASSWORD, database=DB_NAME,
            charset='utf8mb4', connect_timeout=5,
            cursorclass=pymysql.cursors.DictCursor
        )
        connect_time = round((time.time() - start) * 1000, 1)  # ms
        cur = conn.cursor()

        # Server version
        cur.execute("SELECT VERSION() as version")
        version = cur.fetchone()['version']

        # Global status variables
        status_vars = {}
        cur.execute("SHOW GLOBAL STATUS")
        for row in cur.fetchall():
            status_vars[row['Variable_name']] = row['Value']

        # Global variables
        global_vars = {}
        cur.execute("SHOW GLOBAL VARIABLES WHERE Variable_name IN ('max_connections','innodb_buffer_pool_size','key_buffer_size','query_cache_size','tmp_table_size','max_heap_table_size','datadir')")
        for row in cur.fetchall():
            global_vars[row['Variable_name']] = row['Value']

        # Uptime
        uptime_seconds = int(status_vars.get('Uptime', 0))
        days = uptime_seconds // 86400
        hours = (uptime_seconds % 86400) // 3600
        minutes = (uptime_seconds % 3600) // 60

        # Database sizes
        cur.execute("""
            SELECT 
                table_schema AS db_name,
                COUNT(*) AS table_count,
                ROUND(SUM(data_length + index_length) / 1024 / 1024, 2) AS size_mb,
                ROUND(SUM(data_length) / 1024 / 1024, 2) AS data_mb,
                ROUND(SUM(index_length) / 1024 / 1024, 2) AS index_mb,
                SUM(table_rows) AS total_rows
            FROM information_schema.tables
            WHERE table_schema NOT IN ('information_schema', 'performance_schema', 'mysql', 'sys')
            GROUP BY table_schema
            ORDER BY size_mb DESC
        """)
        databases = cur.fetchall()

        # Process list (active connections)
        cur.execute("SHOW PROCESSLIST")
        processes = cur.fetchall()
        active_connections = len(processes)
        sleeping = sum(1 for p in processes if p.get('Command') == 'Sleep')
        active_queries = sum(1 for p in processes if p.get('Command') == 'Query')

        # Table status for our DB
        cur.execute(f"""
            SELECT table_name, table_rows, 
                   ROUND((data_length + index_length) / 1024 / 1024, 2) AS size_mb,
                   update_time
            FROM information_schema.tables 
            WHERE table_schema = %s AND table_type = 'BASE TABLE'
            ORDER BY (data_length + index_length) DESC
            LIMIT 15
        """, (DB_NAME,))
        top_tables = cur.fetchall()

        cur.close()
        conn.close()

        return {
            'connected': True,
            'connect_time_ms': connect_time,
            'version': version,
            'uptime': f"{days}d {hours}h {minutes}m",
            'uptime_seconds': uptime_seconds,
            'connections': {
                'current': active_connections,
                'max': int(global_vars.get('max_connections', 0)),
                'sleeping': sleeping,
                'active_queries': active_queries,
                'total_connections': int(status_vars.get('Connections', 0)),
                'aborted_connects': int(status_vars.get('Aborted_connects', 0)),
            },
            'queries': {
                'total': int(status_vars.get('Questions', 0)),
                'selects': int(status_vars.get('Com_select', 0)),
                'inserts': int(status_vars.get('Com_insert', 0)),
                'updates': int(status_vars.get('Com_update', 0)),
                'deletes': int(status_vars.get('Com_delete', 0)),
                'slow_queries': int(status_vars.get('Slow_queries', 0)),
            },
            'traffic': {
                'bytes_received': int(status_vars.get('Bytes_received', 0)),
                'bytes_sent': int(status_vars.get('Bytes_sent', 0)),
            },
            'innodb': {
                'buffer_pool_size': int(global_vars.get('innodb_buffer_pool_size', 0)),
                'buffer_pool_reads': int(status_vars.get('Innodb_buffer_pool_reads', 0)),
                'buffer_pool_read_requests': int(status_vars.get('Innodb_buffer_pool_read_requests', 0)),
                'row_lock_waits': int(status_vars.get('Innodb_row_lock_waits', 0)),
            },
            'databases': [dict(row) for row in databases],
            'top_tables': [dict(row) for row in top_tables],
        }
    except Exception as e:
        return {'connected': False, 'error': str(e)}


@router.get("/status")
def get_station_status():
    """Get full status of remote server station."""
    return {
        'host': STATION_HOST,
        'ping': ping_host(STATION_HOST),
        'mysql': get_mysql_stats(STATION_HOST),
    }


@router.get("/ping")
def ping_station():
    """Quick ping check of the remote server."""
    return {
        'host': STATION_HOST,
        'ping': ping_host(STATION_HOST, count=1),
    }
