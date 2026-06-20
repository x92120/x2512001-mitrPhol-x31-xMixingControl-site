import paho.mqtt.client as mqtt
import json

payload = {
    "HMI_Command": 1,
    "Step_ID": 4,
    "TT_SP": [60],
    "Agitator_Speed": 1500,
    "High_Shear_SP": 0,
    "Step_Time_SP": 120,
    "Cmd_NewStep": True
}

client = mqtt.Client()
client.connect("192.168.21.212", 1883, 60)
client.publish("mixing/plant/3/step_cmd", json.dumps(payload))
client.disconnect()
print("Published test message to DB1530")
