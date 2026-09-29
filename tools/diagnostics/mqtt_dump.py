import sys
import time
sys.path.append('/home/x-root/xApp/x2512001-mitrPhol-x31-xMixingControl/x3101-app/x3101-0210-backEnd/x0201-fastAPI')
import paho.mqtt.client as mqtt

def on_message(client, userdata, msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg.topic}: {msg.payload.decode()[:200]}")

client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1)
client.on_message = on_message
client.connect("127.0.0.1", 1883)
client.subscribe("#")
client.loop_start()
time.sleep(10)
client.loop_stop()
