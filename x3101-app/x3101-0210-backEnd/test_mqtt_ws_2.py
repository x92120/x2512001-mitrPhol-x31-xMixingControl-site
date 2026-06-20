import paho.mqtt.client as mqtt
import time
def on_message(client, userdata, msg):
    print(msg.topic, msg.payload.decode())
client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1)
client.on_message = on_message
client.username_pw_set("xMixingNode-1", "x123456")
client.connect("127.0.0.1", 1883)
client.subscribe("mixing/plant/1/telemetry")
client.subscribe("mixing/plant/2/telemetry")
client.subscribe("mixing/plant/3/telemetry")
client.loop_start()
time.sleep(5)
client.loop_stop()
