import paho.mqtt.client as mqtt
import time
def on_message(client, userdata, msg):
    print(msg.topic + " " + str(msg.payload.decode('utf-8')))
client = mqtt.Client()
client.on_message = on_message
client.connect("192.168.21.198", 1883, 60)
client.subscribe("/MIX-01")
client.loop_start()
time.sleep(3)
client.loop_stop()
