import paho.mqtt.client as mqtt
import time

def on_message(client, userdata, message):
    print(f"Received message on topic {message.topic}: {message.payload.decode('utf-8')[:100]}")

client = mqtt.Client()
client.username_pw_set("xMixingNode-1", "x123456")
client.on_message = on_message
try:
    client.connect("127.0.0.1", 1883, 60)
    client.subscribe("#")
    client.loop_start()
    time.sleep(3)
    client.loop_stop()
except Exception as e:
    print(f"Failed to connect to MQTT: {e}")
