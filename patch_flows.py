import json
import uuid

def generate_id():
    return uuid.uuid4().hex[:16]

with open('current_flows.json', 'r') as f:
    flows = json.load(f)

# Find the plant_monitor_tab ID
tab_id = next(f['id'] for f in flows if f.get('type') == 'tab' and 'Monitor' in f.get('label', ''))
broker_id = next(f['id'] for f in flows if f.get('type') == 'mqtt-broker' and f.get('name') == 'LOCAL')

# Remove old plant 3 simulator nodes
to_remove = ["inject_plant3", "sim_plant3", "mqtt_out_plant3"]
flows = [f for f in flows if f['id'] not in to_remove]

# 1. Create S7 Endpoint for Plant 3
endpoint_id = generate_id()
flows.append({
    "id": endpoint_id,
    "type": "s7 endpoint",
    "transport": "iso-on-tcp",
    "address": "192.168.21.210",
    "port": "102",
    "rack": "0",
    "slot": "1",
    "localtsaphi": "01",
    "localtsaplo": "00",
    "remotetsaphi": "01",
    "remotetsaplo": "00",
    "connmode": "rack-slot",
    "adapter": "",
    "busaddr": "2",
    "cycletime": "1000",
    "timeout": "2000",
    "name": "Siemens_S7-1200_Plant3",
    "vartable": [
        {"addr": "DB1532,INT0", "name": "watchdog"},
        {"addr": "DB1532,INT2", "name": "plc_state"},
        {"addr": "DB1532,INT4", "name": "current_step"},
        {"addr": "DB1532,INT6", "name": "step_timer"},
        {"addr": "DB1532,REAL8", "name": "mix_temp"},
        {"addr": "DB1532,REAL12", "name": "mix_weight"},
        {"addr": "DB1532,REAL16", "name": "agitator_act"},
        {"addr": "DB1532,REAL20", "name": "highshear_act"},
        {"addr": "DB1532,REAL24", "name": "hopper_weight"},
        
        # DB1530 (Step CMD)
        {"addr": "DB1530,INT22", "name": "HMI_Command"},
        {"addr": "DB1530,INT24", "name": "Step_ID"},
        {"addr": "DB1530,REAL64", "name": "TT_SP"},
        {"addr": "DB1530,REAL76", "name": "Agitator_Speed"},
        {"addr": "DB1530,REAL80", "name": "High_Shear_SP"},
        {"addr": "DB1530,INT84", "name": "Step_Time_SP"},
        {"addr": "DB1530,X86.0", "name": "Cmd_NewStep"}
    ]
})

# 2. Plant 3 Telemetry Flow (S7 In -> Format -> MQTT Out)
s7_in_id = generate_id()
format_id = generate_id()
mqtt_out_id = "mqtt_out_plant3"

flows.extend([
    {
        "id": s7_in_id,
        "type": "s7 in",
        "z": tab_id,
        "endpoint": endpoint_id,
        "mode": "all",
        "name": "Read PLC DB1532",
        "x": 160,
        "y": 320,
        "wires": [[format_id]]
    },
    {
        "id": format_id,
        "type": "function",
        "z": tab_id,
        "name": "Format Plant 3 Status",
        "func": "const plc = msg.payload;\nmsg.payload = {\n    \"Step_no\": Number(plc.current_step || 0),\n    \"Step_Timer\": Number(plc.step_timer || 0),\n    \"Mixing_Tank_Volume\": Number(Number(plc.mix_weight || 0).toFixed(2)),\n    \"Mixing_Tank_Temperature\": Number(Number(plc.mix_temp || 0).toFixed(2)),\n    \"MixingTank_Agitator_Speed\": Number(Number(plc.agitator_act || 0).toFixed(2)),\n    \"HighShare_Speed\": Number(Number(plc.highshear_act || 0).toFixed(2)),\n    \"watchdog\": Number(plc.watchdog || 0),\n    \"PLC_State\": Number(plc.plc_state || 0),\n    \"Hopper_Weight\": Number(Number(plc.hopper_weight || 0).toFixed(2))\n};\nreturn msg;",
        "outputs": 1,
        "x": 380,
        "y": 320,
        "wires": [[mqtt_out_id]]
    },
    {
        "id": mqtt_out_id,
        "type": "mqtt out",
        "z": tab_id,
        "name": "Publish Plant 3",
        "topic": "/MIX-03",
        "qos": "0",
        "retain": "",
        "broker": broker_id,
        "x": 620,
        "y": 320,
        "wires": []
    }
])

# 3. Plant 3 Command Flow (MQTT In -> Format -> S7 Out)
mqtt_in_id = generate_id()
format_cmd_id = generate_id()
s7_out_id = generate_id()

flows.extend([
    {
        "id": mqtt_in_id,
        "type": "mqtt in",
        "z": tab_id,
        "name": "Sub CMD Plant 3",
        "topic": "mixing/plant/3/step_cmd",
        "qos": "0",
        "datatype": "json",
        "broker": broker_id,
        "nl": False,
        "rap": True,
        "rh": 0,
        "inputs": 0,
        "x": 160,
        "y": 400,
        "wires": [[format_cmd_id]]
    },
    {
        "id": format_cmd_id,
        "type": "function",
        "z": tab_id,
        "name": "Parse CMD -> DB1530",
        "func": "const cmd = msg.payload;\nmsg.payload = {\n    \"HMI_Command\": Number(cmd.HMI_Command || 0),\n    \"Step_ID\": Number(cmd.Step_ID || 0),\n    \"TT_SP\": Number((cmd.TT_SP && cmd.TT_SP[0]) ? cmd.TT_SP[0] : 0),\n    \"Agitator_Speed\": Number(cmd.Agitator_Speed || 0),\n    \"High_Shear_SP\": Number(cmd.High_Shear_SP || 0),\n    \"Step_Time_SP\": Number(cmd.Step_Time_SP || 0),\n    \"Cmd_NewStep\": Boolean(cmd.Cmd_NewStep)\n};\nreturn msg;",
        "outputs": 1,
        "x": 380,
        "y": 400,
        "wires": [[s7_out_id]]
    },
    {
        "id": s7_out_id,
        "type": "s7 out",
        "z": tab_id,
        "endpoint": endpoint_id,
        "variable": "",
        "name": "Write DB1530",
        "x": 620,
        "y": 400,
        "wires": []
    }
])

with open('new_flows.json', 'w') as f:
    json.dump(flows, f, indent=4)
