import paho.mqtt.client as mqtt
import json
import time
import datetime
import os

# Configuration
MQTT_HOST = "152.42.166.150"
MQTT_PORT = 1883
MQTT_USER = "admin"
MQTT_PASS = "admin"
MQTT_TOPIC = "#"

LOG_FILE = "mqtt_collection.log"

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print(f"[{datetime.datetime.now()}] Connected to Cloud MQTT successfully!")
        client.subscribe(MQTT_TOPIC)
    else:
        print(f"[{datetime.datetime.now()}] Connection failed with code {rc}")

def on_message(client, userdata, msg):
    try:
        payload = msg.payload.decode()
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Log to console
        print(f"[{timestamp}] {msg.topic}: {payload}")
        
        # Save to file
        log_entry = {
            "timestamp": timestamp,
            "topic": msg.topic,
            "payload": payload
        }
        
        with open(LOG_FILE, "a") as f:
            f.write(json.dumps(log_entry) + "\n")
            
    except Exception as e:
        print(f"Error processing message: {e}")

def run():
    client = mqtt.Client(client_id=f"collector_svc_{int(time.time())}")
    client.username_pw_set(MQTT_USER, MQTT_PASS)
    client.on_connect = on_connect
    client.on_message = on_message

    print(f"Starting MQTT Collector for {MQTT_HOST}...")
    try:
        client.connect(MQTT_HOST, MQTT_PORT, 60)
        client.loop_forever()
    except KeyboardInterrupt:
        print("Stopping collector...")
        client.disconnect()
    except Exception as e:
        print(f"Failed to start: {e}")

if __name__ == "__main__":
    run()
