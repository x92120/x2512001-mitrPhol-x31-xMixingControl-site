#!/bin/bash
# launch-hmi.sh - Safely launch HMI after checking backend/frontend availability

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

echo "Nuxt Frontend is online! Launching $BROWSER in Kiosk mode..." >> "$LOGFILE"

# Disable screen saver blanking
xset s off
# Disable DPMS (Energy Star) standby/suspend/off timeouts
xset -dpms

# Launch Browser with Kiosk flags
exec "$BROWSER" --kiosk --noerrdialogs --disable-infobars --check-for-update-interval=31536000 --simulate-outdated-no-au='Tue, 31 Dec 2099 23:59:59 GMT' "$URL"
