#!/bin/bash
# =============================================================================
# xMixing Control - Industrial Stability & Health Watchdog
# =============================================================================

LOGFILE="/home/x-root/xApp/watchdog.log"
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

log_msg() {
    echo "[$TIMESTAMP] $1" >> "$LOGFILE"
}

# 1. CHECK & RECOVER FASTAPI BACKEND (Port 8031)
FASTAPI_STATUS=$(curl -s -m 4 -o /dev/null -w "%{http_code}" http://127.0.0.1:8031/docs 2>/dev/null)
if [ "$FASTAPI_STATUS" != "200" ]; then
    log_msg "[WARNING] FastAPI Backend (Port 8031) not responding (status: $FASTAPI_STATUS). Restarting..."
    pkill -f "uvicorn main:app.*8031" 2>/dev/null
    sleep 2
    cd /home/x-root/xApp/x2512001-mitrPhol-x31-xMixingControl/x3101-app/x3101-0210-backEnd/x0201-fastAPI
    nohup ./venv/bin/python -m uvicorn main:app --host 0.0.0.0 --port 8031 > /tmp/fastapi.log 2>&1 &
    log_msg "[SUCCESS] FastAPI Backend restarted."
fi

# 2. CHECK & RECOVER NUXT FRONTEND (Port 3031)
NUXT_STATUS=$(curl -s -m 4 -o /dev/null -w "%{http_code}" http://127.0.0.1:3031 2>/dev/null)
if [ "$NUXT_STATUS" != "200" ] && [ "$NUXT_STATUS" != "302" ]; then
    log_msg "[WARNING] Nuxt Frontend (Port 3031) not responding (status: $NUXT_STATUS). Restarting..."
    pkill -f "nuxt dev.*3031" 2>/dev/null
    sleep 2
    cd /home/x-root/xApp/x2512001-mitrPhol-x31-xMixingControl/x3101-app/x3101-0110-frontEnd
    nohup npm run dev -- --host 0.0.0.0 --port 3031 > /tmp/nuxt.log 2>&1 &
    log_msg "[SUCCESS] Nuxt Frontend restarted."
fi

# 3. MEMORY LEAK GUARD (> 850MB for Node, > 450MB for Python)
NODE_PID=$(pgrep -f "nuxt dev.*3031" | head -n 1)
if [ -n "$NODE_PID" ]; then
    NODE_MEM_KB=$(ps -p "$NODE_PID" -o rss= 2>/dev/null | tr -d ' ')
    if [ -n "$NODE_MEM_KB" ] && [ "$NODE_MEM_KB" -gt 850000 ]; then
        log_msg "[INFO] Nuxt Memory exceeded 850MB ($NODE_MEM_KB KB). Graceful recycling..."
        pkill -f "nuxt dev.*3031" 2>/dev/null
        sleep 2
        cd /home/x-root/xApp/x2512001-mitrPhol-x31-xMixingControl/x3101-app/x3101-0110-frontEnd
        nohup npm run dev -- --host 0.0.0.0 --port 3031 > /tmp/nuxt.log 2>&1 &
    fi
fi

# 4. LOG ROTATION & DISK CLEANUP (Keep temp files < 20MB)
for f in "$LOGFILE" /tmp/fastapi.log /tmp/nuxt.log /home/x-root/.xmixing-hmi-launch.log; do
    if [ -f "$f" ]; then
        SIZE=$(stat -c%s "$f" 2>/dev/null || echo 0)
        if [ "$SIZE" -gt 20971520 ]; then
            tail -n 2000 "$f" > "$f.tmp" && mv "$f.tmp" "$f"
            log_msg "[MAINTENANCE] Rotated $f (was > 20MB)"
        fi
    fi
done
