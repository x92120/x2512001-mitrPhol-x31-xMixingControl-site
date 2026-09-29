import json
import uuid

def generate_id():
    return uuid.uuid4().hex[:16]

with open('final_flows.json', 'r') as f:
    flows = json.load(f)

# Find necessary components
tab_id = next(f['id'] for f in flows if f.get('type') == 'tab' and 'Monitor' in f.get('label', ''))
broker_id_local = next(f['id'] for f in flows if f.get('type') == 'mqtt-broker' and f.get('name') == 'LOCAL')
endpoint = next(f for f in flows if f.get('type') == 's7 endpoint' and f['name'] == 'Siemens_S7-1200')

# Remove existing Telemetry Read nodes if they exist (s7 in -> format -> mqtt out)
# Actually, the user says they want to write. Let's just create the write nodes and keep things clean.
# Let's find any nodes that might conflict, or just add new nodes.
# Let's remove the "Read PLC DB1512", "Format Plant 1 Status", "Publish Plant 1" etc.
nodes_to_remove = []
for f in flows:
    name = f.get('name', '')
    if name in [
        'Read PLC DB1512', 'Format Plant 1 Status', 'Publish Plant 1',
        'Read PLC DB1522', 'Format Plant 2 Status', 'Publish Plant 2',
        'Read PLC DB1532', 'Format Plant 3 Status', 'Publish Plant 3',
        'Read PLC DB1512 (Plant 1)', 'Read PLC DB1522 (Plant 2)', 'Read PLC DB1532 (Plant 3)'
    ]:
        nodes_to_remove.append(f['id'])

flows = [f for f in flows if f['id'] not in nodes_to_remove]

# Helper to create write flow
def create_write_flow(plant_id, topic, var_prefix, y_offset):
    mqtt_in = generate_id()
    format_node = generate_id()
    s7_out = generate_id()
    
    flow = [
        {
            "id": mqtt_in,
            "type": "mqtt in",
            "z": tab_id,
            "name": f"Sub Telemetry Plant {plant_id}",
            "topic": topic,
            "qos": "0",
            "datatype": "json",
            "broker": broker_id_local,
            "nl": False,
            "rap": True,
            "rh": 0,
            "inputs": 0,
            "x": 160,
            "y": y_offset,
            "wires": [[format_node]]
        },
        {
            "id": format_node,
            "type": "function",
            "z": tab_id,
            "name": f"Parse Telemetry -> DB15{plant_id}2",
            "func": f"""const act = msg.payload;
const vars = [];
const vals = [];

if (act.watchdog !== undefined) {{ vars.push("{var_prefix}_watchdog"); vals.push(Number(act.watchdog)); }}
if (act.PLC_State !== undefined) {{ vars.push("{var_prefix}_plc_state"); vals.push(Number(act.PLC_State)); }}
if (act.Current_Step !== undefined || act.Step_no !== undefined) {{ vars.push("{var_prefix}_current_step"); vals.push(Number(act.Current_Step || act.Step_no || 0)); }}
if (act.Step_Timer !== undefined) {{ vars.push("{var_prefix}_step_timer"); vals.push(Number(act.Step_Timer)); }}
if (act.MixTank_Temp !== undefined || act.Mixing_Tank_Temperature !== undefined) {{ vars.push("{var_prefix}_mix_temp"); vals.push(Number(act.MixTank_Temp || act.Mixing_Tank_Temperature || 0)); }}
if (act.MixTank_Weight !== undefined || act.Mixing_Tank_Volume !== undefined) {{ vars.push("{var_prefix}_mix_weight"); vals.push(Number(act.MixTank_Weight || act.Mixing_Tank_Volume || 0)); }}
if (act.Agitator_Act !== undefined || act.MixingTank_Agitator_Speed !== undefined) {{ vars.push("{var_prefix}_agitator_act"); vals.push(Number(act.Agitator_Act || act.MixingTank_Agitator_Speed || 0)); }}
if (act.HighShear_Act !== undefined || act.HighShare_Speed !== undefined) {{ vars.push("{var_prefix}_highshear_act"); vals.push(Number(act.HighShear_Act || act.HighShare_Speed || 0)); }}
if (act.Hopper_Weight !== undefined) {{ vars.push("{var_prefix}_hopper_weight"); vals.push(Number(act.Hopper_Weight)); }}

msg.variable = vars;
msg.payload = vals;
return msg;""",
            "outputs": 1,
            "x": 400,
            "y": y_offset,
            "wires": [[s7_out]]
        },
        {
            "id": s7_out,
            "type": "s7 out",
            "z": tab_id,
            "endpoint": endpoint['id'],
            "variable": "",
            "name": f"Write DB15{plant_id}2",
            "x": 640,
            "y": y_offset,
            "wires": []
        }
    ]
    return flow

flows.extend(create_write_flow(1, "/MIX-01", "p1", 800))
flows.extend(create_write_flow(2, "/MIX-02", "p2", 850))
flows.extend(create_write_flow(3, "/MIX-03", "p3", 900))

with open('final_flows.json', 'w') as f:
    json.dump(flows, f, indent=4)

print("Added Telemetry Write flows to final_flows.json")
