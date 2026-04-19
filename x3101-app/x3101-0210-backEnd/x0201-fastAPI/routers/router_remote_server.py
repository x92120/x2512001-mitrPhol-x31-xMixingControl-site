"""
Remote Server Monitoring Router
================================
Provides endpoints to monitor the remote server (192.168.121.11)
via SSH subprocess calls.

Endpoints:
  GET /remote-server/status  → Get CPU, RAM, Disk, Network from remote host
"""

import subprocess
import logging
import os
import re
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/remote-server", tags=["Remote Server Monitoring"])

# Remote server configuration
REMOTE_HOST = os.getenv("REMOTE_SERVER_HOST", "192.168.121.11")
REMOTE_USER = os.getenv("REMOTE_SERVER_USER", "user")
SSH_KEY = os.getenv("REMOTE_SERVER_SSH_KEY", "")  # Optional path to SSH key
SSH_TIMEOUT = int(os.getenv("REMOTE_SERVER_SSH_TIMEOUT", "10"))


def _ssh_command(cmd: str) -> str:
    """Execute a command on the remote server via SSH."""
    ssh_args = [
        "ssh",
        "-o", "StrictHostKeyChecking=no",
        "-o", "ConnectTimeout=5",
        "-o", "BatchMode=yes",
    ]
    if SSH_KEY:
        ssh_args.extend(["-i", SSH_KEY])

    ssh_args.append(f"{REMOTE_USER}@{REMOTE_HOST}")
    ssh_args.append(cmd)

    try:
        result = subprocess.run(
            ssh_args,
            capture_output=True,
            text=True,
            timeout=SSH_TIMEOUT,
        )
        if result.returncode != 0:
            logger.warning(f"SSH command failed: {result.stderr.strip()}")
            return ""
        return result.stdout.strip()
    except subprocess.TimeoutExpired:
        logger.error(f"SSH command timed out: {cmd}")
        return ""
    except Exception as e:
        logger.error(f"SSH error: {e}")
        return ""


def _parse_cpu_info() -> dict:
    """Get CPU info from remote server."""
    # CPU usage from /proc/stat (snapshot approach via top)
    cpu_output = _ssh_command(
        "top -bn1 | head -5 && echo '---CPUINFO---' && "
        "grep 'model name' /proc/cpuinfo | head -1 && "
        "echo '---CPUCOUNT---' && "
        "nproc"
    )

    cpu_average = 0.0
    cpu_model = "Unknown"
    cpu_count = 1

    if cpu_output:
        lines = cpu_output.split("\n")
        for line in lines:
            # Parse: %Cpu(s):  5.9 us,  1.2 sy,  0.0 ni, 92.4 id, ...
            if "%Cpu" in line or "Cpu(s)" in line:
                idle_match = re.search(r'(\d+\.?\d*)\s*(id|idle)', line)
                if idle_match:
                    idle = float(idle_match.group(1))
                    cpu_average = 100.0 - idle
            elif "model name" in line:
                cpu_model = line.split(":")[1].strip() if ":" in line else "Unknown"
            elif line.strip().isdigit():
                cpu_count = int(line.strip())

    # Per-CPU usage via mpstat or fallback
    cpu_percents = []
    per_cpu_output = _ssh_command(
        "cat /proc/stat | grep '^cpu[0-9]'"
    )
    if per_cpu_output:
        for line in per_cpu_output.split("\n"):
            parts = line.split()
            if len(parts) >= 5 and parts[0].startswith("cpu"):
                user = int(parts[1])
                nice = int(parts[2])
                system = int(parts[3])
                idle_val = int(parts[4])
                iowait = int(parts[5]) if len(parts) > 5 else 0
                total = user + nice + system + idle_val + iowait
                if total > 0:
                    usage = ((total - idle_val - iowait) / total) * 100
                    cpu_percents.append(round(usage, 1))

    return {
        "cpu_average": round(cpu_average, 1),
        "cpu_count": cpu_count,
        "cpu_model": cpu_model,
        "cpu_percent": cpu_percents[:cpu_count],
    }


def _parse_memory_info() -> dict:
    """Get memory info from /proc/meminfo."""
    output = _ssh_command("cat /proc/meminfo")

    mem = {"total": 0, "available": 0, "used": 0, "percent": 0.0}

    if output:
        values = {}
        for line in output.split("\n"):
            parts = line.split(":")
            if len(parts) == 2:
                key = parts[0].strip()
                val_parts = parts[1].strip().split()
                values[key] = int(val_parts[0]) * 1024  # Convert kB to bytes

        total = values.get("MemTotal", 0)
        available = values.get("MemAvailable", values.get("MemFree", 0))
        used = total - available

        mem = {
            "total": total,
            "available": available,
            "used": used,
            "percent": round((used / total * 100), 1) if total > 0 else 0.0,
        }

    return mem


def _parse_disk_info() -> dict:
    """Get disk usage from df."""
    output = _ssh_command("df -B1 / | tail -1")

    disk = {"total": 0, "used": 0, "free": 0, "percent": 0.0}

    if output:
        parts = output.split()
        if len(parts) >= 4:
            disk = {
                "total": int(parts[1]),
                "used": int(parts[2]),
                "free": int(parts[3]),
                "percent": round(int(parts[2]) / int(parts[1]) * 100, 1) if int(parts[1]) > 0 else 0.0,
            }

    return disk


def _parse_network_info() -> dict:
    """Get network stats from /proc/net/dev."""
    output = _ssh_command("cat /proc/net/dev")

    net = {"bytes_sent": 0, "bytes_recv": 0, "packets_sent": 0, "packets_recv": 0}

    if output:
        for line in output.split("\n"):
            line = line.strip()
            if ":" in line and not line.startswith("Inter") and not line.startswith("face"):
                iface, data = line.split(":", 1)
                iface = iface.strip()
                if iface == "lo":
                    continue
                parts = data.split()
                if len(parts) >= 10:
                    net["bytes_recv"] += int(parts[0])
                    net["packets_recv"] += int(parts[1])
                    net["bytes_sent"] += int(parts[8])
                    net["packets_sent"] += int(parts[9])

    return net


def _parse_uptime() -> dict:
    """Get uptime and hostname."""
    hostname = _ssh_command("hostname") or "unknown"
    os_info = _ssh_command("uname -sr") or "Linux"
    architecture = _ssh_command("uname -m") or "unknown"
    uptime_raw = _ssh_command("cat /proc/uptime")
    boot_time = 0.0

    if uptime_raw:
        uptime_secs = float(uptime_raw.split()[0])
        import time
        boot_time = time.time() - uptime_secs

    # Get Python version on remote
    python_version = _ssh_command("python3 --version 2>/dev/null || python --version 2>/dev/null") or "N/A"
    python_version = python_version.replace("Python ", "")

    # Get local IP
    local_ip = _ssh_command("hostname -I | awk '{print $1}'") or REMOTE_HOST

    return {
        "hostname": hostname,
        "os": os_info,
        "architecture": architecture,
        "boot_time": boot_time,
        "python_version": python_version,
        "local_ip": local_ip,
    }


@router.get("/status")
def get_remote_server_status():
    """
    Get full system status from the remote server via SSH.
    Returns CPU, Memory, Disk, Network, and system info.
    """
    # Test SSH connectivity first
    test = _ssh_command("echo ok")
    if test != "ok":
        raise HTTPException(
            status_code=503,
            detail=f"Cannot connect to remote server {REMOTE_HOST} via SSH"
        )

    cpu_info = _parse_cpu_info()
    memory = _parse_memory_info()
    disk = _parse_disk_info()
    network = _parse_network_info()
    system = _parse_uptime()

    return {
        "host": REMOTE_HOST,
        "cpu_percent": cpu_info["cpu_percent"],
        "cpu_average": cpu_info["cpu_average"],
        "cpu_count": cpu_info["cpu_count"],
        "cpu_model": cpu_info["cpu_model"],
        "memory": memory,
        "disk": disk,
        "network": network,
        "boot_time": system["boot_time"],
        "os": system["os"],
        "python_version": system["python_version"],
        "hostname": system["hostname"],
        "local_ip": system["local_ip"],
        "architecture": system["architecture"],
    }


@router.get("/ping")
def ping_remote_server():
    """Quick check if remote server is reachable via SSH."""
    test = _ssh_command("echo ok")
    return {
        "host": REMOTE_HOST,
        "reachable": test == "ok",
    }
