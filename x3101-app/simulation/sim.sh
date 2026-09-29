#!/bin/bash
# ============================================================
#  xMixing SIM Environment — Start/Stop Scripts
#  PLCSIM Advanced V16 @ 192.168.21.220
# ============================================================

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_DIR="$SCRIPT_DIR"
BACKEND_DIR="$APP_DIR/x3101-0210-backEnd/x0201-fastAPI"
FRONTEND_DIR="$APP_DIR/x3101-0110-frontEnd"
VENV="$BACKEND_DIR/venv/bin/python"

case "$1" in
  start)
    echo "🚀 Starting xMixing SIM Environment..."

    # 1. Node-RED SIM
    echo "  [1/3] Starting Node-RED SIM (port 1882)..."
    docker compose -f "$APP_DIR/docker-compose.sim.yml" up -d
    echo "       Node-RED SIM → http://localhost:1882"

    # 2. Backend SIM
    echo "  [2/3] Starting Backend SIM (port 8032)..."
    cd "$BACKEND_DIR"
    ENV_FILE="$BACKEND_DIR/.env.sim" \
    $VENV -m uvicorn main:app \
      --host 0.0.0.0 \
      --port 8032 \
      --env-file "$BACKEND_DIR/.env.sim" \
      --reload > "$APP_DIR/backend_sim.log" 2>&1 &
    echo $! > /tmp/xmixing_backend_sim.pid
    echo "       Backend SIM → http://localhost:8032"

    # 3. Frontend SIM
    echo "  [3/3] Starting Frontend SIM (port 3032)..."
    cd "$FRONTEND_DIR"
    cp .env .env.bak 2>/dev/null
    NODE_ENV=development \
    NUXT_PUBLIC_API_BASE=http://localhost:8032 \
    VITE_SIM_MODE=true \
    VITE_PLANT1_CMD=sim/plant/1/step_cmd \
    VITE_PLANT2_CMD=sim/plant/2/step_cmd \
    VITE_PLANT3_CMD=sim/plant/3/step_cmd \
    VITE_PLANT1_TOPIC=/SIM-01 \
    VITE_PLANT2_TOPIC=/SIM-02 \
    VITE_PLANT3_TOPIC=/SIM-03 \
    npx nuxt dev --host 0.0.0.0 --port 3032 > "$APP_DIR/frontend_sim.log" 2>&1 &
    echo $! > /tmp/xmixing_frontend_sim.pid
    echo "       Frontend SIM → http://localhost:3032"

    echo ""
    echo "✅ SIM Environment Started!"
    echo "   🌐 Frontend  : http://$(hostname -I | awk '{print $1}'):3032"
    echo "   🔧 Backend   : http://$(hostname -I | awk '{print $1}'):8032"
    echo "   🔴 Node-RED  : http://$(hostname -I | awk '{print $1}'):1882"
    echo "   🤖 PLCSIM    : 192.168.21.220"
    echo ""
    echo "   Production ยังทำงานปกติที่ port 3031/8031/1880"
    ;;

  stop)
    echo "🛑 Stopping xMixing SIM Environment..."

    # หยุด Node-RED SIM
    docker compose -f "$APP_DIR/docker-compose.sim.yml" down

    # หยุด Backend SIM
    if [ -f /tmp/xmixing_backend_sim.pid ]; then
      kill $(cat /tmp/xmixing_backend_sim.pid) 2>/dev/null
      rm /tmp/xmixing_backend_sim.pid
      echo "  Backend SIM stopped"
    fi

    # หยุด Frontend SIM
    if [ -f /tmp/xmixing_frontend_sim.pid ]; then
      kill $(cat /tmp/xmixing_frontend_sim.pid) 2>/dev/null
      rm /tmp/xmixing_frontend_sim.pid
      echo "  Frontend SIM stopped"
    fi

    echo "✅ SIM Environment Stopped. Production unaffected."
    ;;

  status)
    echo "=== xMixing SIM Status ==="
    echo ""
    # Node-RED SIM
    docker ps --filter "name=node-red-sim" --format "  Node-RED SIM: {{.Status}}" 2>/dev/null || echo "  Node-RED SIM: not running"
    # Backend SIM
    if [ -f /tmp/xmixing_backend_sim.pid ] && kill -0 $(cat /tmp/xmixing_backend_sim.pid) 2>/dev/null; then
      echo "  Backend SIM : running (PID $(cat /tmp/xmixing_backend_sim.pid))"
    else
      echo "  Backend SIM : not running"
    fi
    # Frontend SIM
    if [ -f /tmp/xmixing_frontend_sim.pid ] && kill -0 $(cat /tmp/xmixing_frontend_sim.pid) 2>/dev/null; then
      echo "  Frontend SIM: running (PID $(cat /tmp/xmixing_frontend_sim.pid))"
    else
      echo "  Frontend SIM: not running"
    fi
    echo ""
    # PLCSIM ping
    ping -c 1 -W 1 192.168.21.220 >/dev/null 2>&1 \
      && echo "  PLCSIM Adv  : ✅ Online (192.168.21.220)" \
      || echo "  PLCSIM Adv  : ❌ Offline (192.168.21.220)"
    ;;

  *)
    echo "Usage: $0 {start|stop|status}"
    echo ""
    echo "  start  — เริ่ม SIM environment (Node-RED:1882, Backend:8032, Frontend:3032)"
    echo "  stop   — หยุด SIM environment"
    echo "  status — ดูสถานะ"
    exit 1
    ;;
esac
