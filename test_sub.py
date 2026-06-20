import paho.mqtt.client as mqtt
def on_message(c, u, msg): print(f"Got {msg.topic}: {msg.payload}")
client = mqtt.Client()
client.username_pw_set("xMixingNode-1", "x123456")
client.on_message = on_message
client.connect("127.0.0.1", 1883)
client.subscribe("mixing/#")
client.loop_start()
import time; time.sleep(5)
