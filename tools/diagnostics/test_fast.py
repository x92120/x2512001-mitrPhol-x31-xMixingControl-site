import paho.mqtt.client as mqtt
import json
import time
def on_connect(client, userdata, flags, rc):
    print("Connected")
    client.subscribe("MIX-01-PUT")
def on_message(client, userdata, msg):
    pass
client = mqtt.Client(transport="websockets")
client.username_pw_set("xMixingNode-1", "x123456")
client.on_connect = on_connect
client.on_message = on_message
client.connect("172.20.0.2", 15675, 60)
client.loop_start()
time.sleep(1)
for i in range(100):
    client.publish("MIX-01-PUT", json.dumps({"test": i}))
    time.sleep(0.01)
time.sleep(2)
print("Done")
