import json
import uuid
import requests

def generate_id():
    return uuid.uuid4().hex[:16]

with open('final_flows.json', 'r') as f:
    flows = json.load(f)

# Find necessary IDs
tab_id = next(f['id'] for f in flows if f.get('type') == 'tab' and 'Monitor' in f.get('label', ''))
broker_id = next(f['id'] for f in flows if f.get('type') == 'mqtt-broker' and f.get('name') == 'LOCAL')
endpoint = next(f for f in flows if f.get('type') == 's7 endpoint' and f['name'] == 'Siemens_S7-1200')
endpoint_id = endpoint['id']

# Function template
format_func = """const plc = msg.payload;
msg.payload = {
    "Current_Step": Number(plc["p{plant_id}_current_step"] || 0),
    "Step_no": Number(plc["p{plant_id}_current_step"] || 0),
    "Step_Timer": Number(plc["p{plant_id}_step_timer"] || 0),
    "Mixing_Tank_Volume": Number(Number(plc["p{plant_id}_mix_weight"] || 0).toFixed(2)),
    "Mixing_Tank_Temperature": Number(Number(plc["p{plant_id}_mix_temp"] || 0).toFixed(2)),
    "MixingTank_Agitator_Speed": Number(Number(plc["p{plant_id}_agitator_act"] || 0).toFixed(2)),
    "HighShare_Speed": Number(Number(plc["p{plant_id}_highshear_act"] || 0).toFixed(2)),
    "watchdog": Number(plc["p{plant_id}_watchdog"] || 0),
    "PLC_State": Number(plc["p{plant_id}_plc_state"] || 0),
    "Hopper_Weight": Number(Number(plc["p{plant_id}_hopper_weight"] || 0).toFixed(2))
};
return msg;"""

# Add flows for Plant 1, 2, 3
for plant_id, y_offset in [(1, 100), (2, 200), (3, 300)]:
    s7_in_id = generate_id()
    format_id = generate_id()
    mqtt_out_id = generate_id()
    
    # Check if this node already exists
    if any(f.get('name') == f"Read PLC DB15{plant_id}2" for f in flows):
        print(f"Flow for Plant {plant_id} already exists, skipping...")
        continue

    flows.extend([
        {
            "id": s7_in_id,
            "type": "s7 in",
            "z": tab_id,
            "endpoint": endpoint_id,
            "mode": "all",
            "name": f"Read PLC DB15{plant_id}2",
            "x": 160,
            "y": y_offset,
            "wires": [[format_id]]
        },
        {
            "id": format_id,
            "type": "function",
            "z": tab_id,
            "name": f"Format Plant {plant_id} Status",
            "func": format_func.replace("{plant_id}", str(plant_id)),
            "outputs": 1,
            "x": 380,
            "y": y_offset,
            "wires": [[mqtt_out_id]]
        },
        {
            "id": mqtt_out_id,
            "type": "mqtt out",
            "z": tab_id,
            "name": f"Publish Plant {plant_id}",
            "topic": f"/MIX-0{plant_id}",
            "qos": "0",
            "retain": "",
            "broker": broker_id,
            "x": 620,
            "y": y_offset,
            "wires": []
        }
    ])

with open('final_flows.json', 'w') as f:
    json.dump(flows, f, indent=4)

r = requests.post('http://localhost:1880/flows', json=flows)
print("Deploy status:", r.status_code)
