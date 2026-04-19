"""
Monitoring Router
=================
Server status and monitoring endpoints.
"""

from fastapi import APIRouter
from typing import List
import psutil
import platform
import sys
import os
import logging

from influxdb_client import InfluxDBClient

import schemas

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Monitoring"])

# InfluxDB Configuration
INFLUX_URL = os.getenv("INFLUX_URL", "http://localhost:8086")
INFLUX_TOKEN = os.getenv("INFLUX_TOKEN", "mysecrettoken")
INFLUX_ORG = os.getenv("INFLUX_ORG", "myorg")
INFLUX_BUCKET = os.getenv("INFLUX_BUCKET", "server_monitor")


@router.get("/host-info", response_model=schemas.HostInfo)
def get_host_info():
    """Get host machine information."""
    import socket
    import subprocess
    from datetime import datetime, timezone

    # Get hostname
    hostname = socket.gethostname()

    # Get IP addresses
    try:
        result = subprocess.run(['hostname', '-I'], capture_output=True, text=True, timeout=5)
        ip_addresses = [ip.strip() for ip in result.stdout.strip().split() if ip.strip()]
    except Exception:
        ip_addresses = [socket.gethostbyname(hostname)]

    # Get CPU model
    cpu_model = "Unknown"
    try:
        with open('/proc/cpuinfo', 'r') as f:
            for line in f:
                if 'model name' in line:
                    cpu_model = line.split(':')[1].strip()
                    break
    except Exception:
        cpu_model = platform.processor() or "Unknown"

    # Get uptime
    boot_ts = psutil.boot_time()
    boot_dt = datetime.fromtimestamp(boot_ts, tz=timezone.utc)
    uptime_seconds = (datetime.now(tz=timezone.utc) - boot_dt).total_seconds()
    days = int(uptime_seconds // 86400)
    hours = int((uptime_seconds % 86400) // 3600)
    minutes = int((uptime_seconds % 3600) // 60)
    uptime_str = f"{days}d {hours}h {minutes}m"

    # Total RAM
    mem = psutil.virtual_memory()
    total_gb = mem.total / (1024 ** 3)

    return {
        "hostname": hostname,
        "ip_addresses": ip_addresses,
        "os_name": platform.system(),
        "os_version": platform.version(),
        "kernel": platform.release(),
        "architecture": platform.machine(),
        "cpu_model": cpu_model,
        "total_ram": f"{total_gb:.1f} GB",
        "username": os.getenv("USER", os.getenv("USERNAME", "unknown")),
        "uptime": uptime_str,
        "boot_time_iso": boot_dt.isoformat(),
    }


@router.get("/connected-devices", response_model=schemas.ConnectedDevices)
def get_connected_devices():
    """Get devices connected to this system (USB, Network interfaces, Serial ports)."""
    import subprocess
    import glob

    usb_devices = []
    network_devices = []
    serial_devices = []

    # USB Devices
    try:
        result = subprocess.run(
            ['lsusb'], capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            for line in result.stdout.strip().split('\n'):
                if line.strip():
                    # Parse: Bus 001 Device 002: ID 1234:5678 Device Name
                    parts = line.split('ID ')
                    name = parts[1].strip() if len(parts) > 1 else line.strip()
                    # Skip root hubs
                    if 'root hub' in name.lower():
                        continue
                    usb_devices.append({
                        "name": name,
                        "type": "usb",
                        "status": "connected",
                        "details": line.strip(),
                        "icon": "usb"
                    })
    except Exception as e:
        logger.warning(f"Failed to list USB devices: {e}")

    # Network Interfaces
    try:
        net_if = psutil.net_if_addrs()
        net_stats = psutil.net_if_stats()
        for iface_name, addrs in net_if.items():
            if iface_name == 'lo':
                continue  # Skip loopback
            stat = net_stats.get(iface_name)
            is_up = stat.isup if stat else False
            ip_addr = ""
            for addr in addrs:
                if addr.family.name == 'AF_INET':
                    ip_addr = addr.address
                    break
            speed_info = f"{stat.speed}Mbps" if stat and stat.speed > 0 else "N/A"
            network_devices.append({
                "name": iface_name,
                "type": "network",
                "status": "up" if is_up else "down",
                "details": f"IP: {ip_addr or 'N/A'} | Speed: {speed_info}",
                "icon": "wifi" if "wl" in iface_name else "settings_ethernet"
            })
    except Exception as e:
        logger.warning(f"Failed to list network interfaces: {e}")

    # Serial Devices (scales, scanners, etc.)
    try:
        serial_ports = glob.glob('/dev/ttyUSB*') + glob.glob('/dev/ttyACM*') + glob.glob('/dev/ttyS*')
        for port in sorted(serial_ports):
            # Only show ttyS ports that are likely real (skip ttyS4+)
            if '/dev/ttyS' in port:
                port_num = int(port.replace('/dev/ttyS', ''))
                if port_num >= 4:
                    continue
            serial_devices.append({
                "name": port.split('/')[-1],
                "type": "serial",
                "status": "available",
                "details": port,
                "icon": "serial_port" if "ttyUSB" in port else "settings_input_component"
            })
    except Exception as e:
        logger.warning(f"Failed to list serial devices: {e}")

    return {
        "usb_devices": usb_devices,
        "network_devices": network_devices,
        "serial_devices": serial_devices,
    }


@router.get("/server-status", response_model=schemas.ServerStatus)
def get_server_status():
    """Get system resource usage statistics."""
    cpu_percent = psutil.cpu_percent(interval=0.1, percpu=True)
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage('/')
    net = psutil.net_io_counters()

    # Get local IP
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
    except Exception:
        local_ip = "127.0.0.1"

    # Get CPU Model
    import platform
    cpu_model = platform.processor()
    if not cpu_model:
        try:
            # Fallback for Linux
            with open("/proc/cpuinfo", "r") as f:
                for line in f:
                    if "model name" in line:
                        cpu_model = line.split(":")[1].strip()
                        break
        except Exception:
            cpu_model = "Unknown"

    return {
        "cpu_percent": cpu_percent,
        "cpu_average": sum(cpu_percent) / len(cpu_percent) if cpu_percent else 0,
        "cpu_count": psutil.cpu_count(),
        "memory": {
            "total": memory.total,
            "available": memory.available,
            "percent": memory.percent,
            "used": memory.used
        },
        "disk": {
            "total": disk.total,
            "used": disk.used,
            "free": disk.free,
            "percent": disk.percent
        },
        "network": {
            "bytes_sent": net.bytes_sent,
            "bytes_recv": net.bytes_recv,
            "packets_sent": net.packets_sent,
            "packets_recv": net.packets_recv
        },
        "boot_time": psutil.boot_time(),
        "os": f"{platform.system()} {platform.release()}",
        "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        "hostname": socket.gethostname(),
        "local_ip": local_ip,
        "cpu_model": cpu_model,
        "architecture": platform.machine()
    }


@router.get("/server-status/history", response_model=schemas.ServerHistory)
def get_server_history():
    """Get historical system metrics from InfluxDB."""
    try:
        client = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)
        query_api = client.query_api()

        def execute_query(query: str) -> list:
            tables = query_api.query(query)
            return [{"timestamp": r.get_time(), "value": r.get_value()} 
                    for table in tables for r in table.records]

        queries = {
            "cpu": f'from(bucket: "{INFLUX_BUCKET}") |> range(start: -1h) |> filter(fn: (r) => r["_measurement"] == "cpu") |> filter(fn: (r) => r["_field"] == "usage_idle") |> filter(fn: (r) => r["cpu"] == "cpu-total") |> map(fn: (r) => ({{_time: r._time, _value: 100.0 - r._value}}))',
            "memory": f'from(bucket: "{INFLUX_BUCKET}") |> range(start: -1h) |> filter(fn: (r) => r["_measurement"] == "mem") |> filter(fn: (r) => r["_field"] == "used_percent")',
            "disk": f'from(bucket: "{INFLUX_BUCKET}") |> range(start: -1h) |> filter(fn: (r) => r["_measurement"] == "disk") |> filter(fn: (r) => r["path"] == "/") |> filter(fn: (r) => r["_field"] == "used_percent")',
            "net_sent": f'from(bucket: "{INFLUX_BUCKET}") |> range(start: -1h) |> filter(fn: (r) => r["_measurement"] == "net") |> filter(fn: (r) => r["_field"] == "bytes_sent") |> derivative(unit: 1s, nonNegative: true)',
            "net_recv": f'from(bucket: "{INFLUX_BUCKET}") |> range(start: -1h) |> filter(fn: (r) => r["_measurement"] == "net") |> filter(fn: (r) => r["_field"] == "bytes_recv") |> derivative(unit: 1s, nonNegative: true)',
        }

        result = {k: execute_query(v) for k, v in queries.items()}
        client.close()
        return result
    except Exception as e:
        logger.error(f"InfluxDB query error: {e}")
        return {"cpu": [], "memory": [], "disk": [], "net_sent": [], "net_recv": []}
