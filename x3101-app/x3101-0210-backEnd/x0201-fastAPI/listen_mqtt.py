import paho.mqtt.client as mqtt
import time

msgs = []
def on_message(client, userdata, message):
    msgs.append(message.payload.decode('utf-8'))

client = mqtt.Client()
client.on_message = on_message
client.connect("192.168.21.212", 1883, 60)
client.subscribe("mixing/plant/3/step_cmd")
client.loop_start()
print("Listening for 10 seconds...")
time.sleep(10)
client.loop_stop()
if msgs:
    print("Received:", msgs)
else:
    print("No messages received")
