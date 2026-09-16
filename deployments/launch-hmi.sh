#!/bin/bash
# launch-hmi.sh - Safely launch HMI with Memory Management & GPU Acceleration

URL="http://localhost:3031"
LOGFILE="/home/x-root/.xmixing-hmi-launch.log"

echo "=== HMI Autostart Initiated at $(date) ===" >> "$LOGFILE"

# Loop until curl successfully connects to the Nuxt frontend
until curl -s -o /dev/null -w "%{http_code}" "$URL" | grep -E "200|302" > /dev/null; do
  echo "Nuxt Frontend at $URL is not ready yet. Waiting 2 seconds..." >> "$LOGFILE"
  sleep 2
done

# Detect installed browser dynamically
if which google-chrome > /dev/null 2>&1; then
  BROWSER="google-chrome"
elif which google-chrome-stable > /dev/null 2>&1; then
  BROWSER="google-chrome-stable"
elif which chromium-browser > /dev/null 2>&1; then
  BROWSER="chromium-browser"
else
  BROWSER="chromium"
fi

echo "Nuxt Frontend is online! Launching $BROWSER in optimized Kiosk mode..." >> "$LOGFILE"

# Disable screen saver blanking
xset s off 2>/dev/null
# Disable DPMS (Energy Star) standby/suspend/off timeouts
xset -dpms 2>/dev/null

# Launch Browser with Kiosk flags and aggressive memory/GPU optimization
exec "$BROWSER" \
  --kiosk \
  --app="$URL" \
  --js-flags="--max-old-space-size=512" \
  --disk-cache-size=1 \
  --media-cache-size=1 \
  --disable-dev-shm-usage \
  --enable-gpu-rasterization \
  --enable-zero-copy \
  --noerrdialogs \
  --disable-infobars \
  --no-first-run \
  --check-for-update-interval=31536000 \
  --simulate-outdated-no-au='Tue, 31 Dec 2099 23:59:59 GMT' \
  --disable-pinch \
  --overscroll-history-navigation=0 \
  "$URL"
