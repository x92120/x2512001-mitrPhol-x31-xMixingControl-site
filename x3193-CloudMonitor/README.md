# Cloud MQTT Collector & Monitor

This application provides two ways to collect and monitor data from the Mitr Phol Cloud RabbitMQ instance (`152.42.166.150`).

## 1. Web Monitor (Real-time Dashboard)
A high-performance, visually immersive web interface to monitor mixing plant data in real-time.

- **File:** `index.html`
- **Technology:** HTML5, Vanilla CSS (Glassmorphism), MQTT.js (WebSockets)
- **How to use:** Simply open `index.html` in any modern web browser.
- **Features:**
  - Real-time gauges for Plants 1, 2, and 3.
  - Live message traffic stream.
  - Connection status monitoring.

## 2. Background Collector (Data Logger)
A Python-based service for long-term data collection and logging.

- **File:** `collector.py`
- **Technology:** Python, Paho-MQTT
- **How to use:**
  ```bash
  pip install paho-mqtt
  python3 collector.py
  ```
- **Output:** Saves all incoming messages to `mqtt_collection.log` in JSON format.

## Connection Details
- **Host:** `152.42.166.150`
- **MQTT Port:** `1883`
- **Web MQTT Port:** `15675`
- **Credentials:** `admin` / `admin`
