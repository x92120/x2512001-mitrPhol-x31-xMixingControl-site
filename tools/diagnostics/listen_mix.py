import paho.mqtt.client as mqtt
import time
def on_message(client, userdata, msg):
    print(msg.topic, msg.payload.decode())
client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1)
client.on_message = on_message
client.username_pw_set("xMixingNode-1", "x123456")
client.connect("127.0.0.1", 1883)
client.subscribe("/MIX-01")
client.subscribe("/MIX-02")
client.subscribe("/MIX-03")
client.loop_start()
time.sleep(10)
client.loop_stop()
