import paho.mqtt.client as mqtt
import json
import time

# Simulation Script for Industrial Scanner MQTT
BROKER = "127.0.0.1"
PORT = 1883 # Standard MQTT port (RabbitMQ MQTT plugin usually listens here too)
USER = "xMixingNode-1"
PASS = "x123456"

client = mqtt.Client(userdata="scanner-sim")
client.username_pw_set(USER, PASS)

def simulate_scans():
    scans = [
        '{"b:P260411-021-05FV045A-1","m:126450241100026","p:1/","n:0.132,"t:0.132}',
        '{"b":P260411-021-027CL001A-1","m":1275004100003,"p":1/","n":0.24,"t":0.24}',
        '{"b":P260411-021-032CL001A-1","m":1275004100003,"p":1/","n":0.24,"t":0.24}'
    ]
    
    try:
        client.connect(BROKER, PORT, 60)
        client.loop_start()
        
        for i, scan in enumerate(scans):
            topic = f"mixing/plant/{i+1}"
            print(f"🚀 Publishing to {topic}: {scan}")
            client.publish(topic, scan)
            time.sleep(2)
            
        client.loop_stop()
        client.disconnect()
        print("✅ Simulation complete.")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    simulate_scans()
