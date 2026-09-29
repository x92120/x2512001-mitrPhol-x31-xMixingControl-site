import paho.mqtt.publish as publish
import paho.mqtt.client as mqtt

broker = "127.0.0.1"
port = 1883

topics_to_clear = [
    "/MIX-01", "/MIX-02", "/MIX-03",
    "mixing/plant/1/telemetry", "mixing/plant/2/telemetry", "mixing/plant/3/telemetry",
    "MIX01.MIS_REQ", "MIX01.TEMP01", "MIX01.IBC_REQ", "MIX01.LS_REQ", "MIX01.RO_REQ",
    "MIX01.TEMP02", "MIX01.TEMP03"
]

msgs = []
for t in topics_to_clear:
    msgs.append({'topic': t, 'payload': b'', 'retain': True, 'qos': 1})

publish.multiple(msgs, hostname=broker, port=port, auth={'username': 'xMixingNode-1', 'password': 'x123456'})
print("Cleared retained messages!")
