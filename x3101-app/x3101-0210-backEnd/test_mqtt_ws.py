import paho.mqtt.client as mqtt
import time
import json

def on_connect(client, userdata, flags, rc):
    print("Connected with result code " + str(rc))
    client.subscribe("MIX-01-PUT")
    print("Publishing...")
    client.publish("MIX-01-PUT", json.dumps({"watch_dog": 1}))

def on_message(client, userdata, msg):
    print("Received:", msg.topic, msg.payload)

def on_disconnect(client, userdata, rc):
    print("Disconnected with result code " + str(rc))

client = mqtt.Client(transport="websockets")
client.ws_set_options(path="/ws")
client.username_pw_set("xMixingNode-1", "x123456")
client.on_connect = on_connect
client.on_message = on_message
client.on_disconnect = on_disconnect

client.connect("127.0.0.1", 15675, 60)
client.loop_start()

time.sleep(5)
client.loop_stop()
