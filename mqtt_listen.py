import paho.mqtt.client as mqtt
import time

def on_message(client, userdata, message):
    print(f"Topic: {message.topic} | Payload: {message.payload.decode()}")

client = mqtt.Client()
client.on_message = on_message
client.connect("127.0.0.1", 1883)
client.subscribe("#")
client.loop_start()
time.sleep(3)
client.loop_stop()
