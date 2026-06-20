import json
import uuid

def generate_id():
    return uuid.uuid4().hex[:16]

with open('new_flows.json', 'r') as f:
    flows = json.load(f)

tab_id = next(f['id'] for f in flows if f.get('type') == 'tab' and 'Monitor' in f.get('label', ''))
broker_id = next(f['id'] for f in flows if f.get('type') == 'mqtt-broker' and f.get('name') == 'LOCAL')
endpoint = next(f for f in flows if f.get('type') == 's7 endpoint' and f['name'] == 'Siemens_S7-1200')

# 1. Clean up old Plant 2 sim nodes
to_remove = ["inject_plant2", "sim_plant2", "mqtt_out_plant2"]
flows = [f for f in flows if f['id'] not in to_remove]

# 2. Rebuild the entire vartable with proper prefixes to avoid clashes!
vartable = [
    # Plant 1 Telemetry (DB1512)
    {"addr": "DB1512,INT0", "name": "p1_watchdog"},
    {"addr": "DB1512,INT2", "name": "p1_plc_state"},
    {"addr": "DB1512,INT4", "name": "p1_current_step"},
    {"addr": "DB1512,INT6", "name": "p1_step_timer"},
    {"addr": "DB1512,REAL8", "name": "p1_mix_temp"},
    {"addr": "DB1512,REAL12", "name": "p1_mix_weight"},
    {"addr": "DB1512,REAL16", "name": "p1_agitator_act"},
    {"addr": "DB1512,REAL20", "name": "p1_highshear_act"},
    {"addr": "DB1512,REAL24", "name": "p1_hopper_weight"},
    
    # Plant 1 Command (DB1510)
    {"addr": "DB1510,STRING0.20", "name": "p1_Batch_ID"},
    {"addr": "DB1510,INT22", "name": "p1_HMI_Command"},
    {"addr": "DB1510,INT24", "name": "p1_Step_ID"},
    {"addr": "DB1510,STRING26.10", "name": "p1_Phase_ID"},
    {"addr": "DB1510,STRING38.20", "name": "p1_Re_Code"},
    {"addr": "DB1510,REAL60", "name": "p1_Target_Weight"},
    {"addr": "DB1510,REAL64", "name": "p1_TT_SP"},
    {"addr": "DB1510,REAL76", "name": "p1_Agitator_Speed"},
    {"addr": "DB1510,REAL80", "name": "p1_High_Shear_SP"},
    {"addr": "DB1510,INT84", "name": "p1_Step_Time_SP"},
    {"addr": "DB1510,X86.0", "name": "p1_Cmd_NewStep"},

    # Plant 2 Telemetry (DB1522)
    {"addr": "DB1522,INT0", "name": "p2_watchdog"},
    {"addr": "DB1522,INT2", "name": "p2_plc_state"},
    {"addr": "DB1522,INT4", "name": "p2_current_step"},
    {"addr": "DB1522,INT6", "name": "p2_step_timer"},
    {"addr": "DB1522,REAL8", "name": "p2_mix_temp"},
    {"addr": "DB1522,REAL12", "name": "p2_mix_weight"},
    {"addr": "DB1522,REAL16", "name": "p2_agitator_act"},
    {"addr": "DB1522,REAL20", "name": "p2_highshear_act"},
    {"addr": "DB1522,REAL24", "name": "p2_hopper_weight"},
    
    # Plant 2 Command (DB1520)
    {"addr": "DB1520,STRING0.20", "name": "p2_Batch_ID"},
    {"addr": "DB1520,INT22", "name": "p2_HMI_Command"},
    {"addr": "DB1520,INT24", "name": "p2_Step_ID"},
    {"addr": "DB1520,STRING26.10", "name": "p2_Phase_ID"},
    {"addr": "DB1520,STRING38.20", "name": "p2_Re_Code"},
    {"addr": "DB1520,REAL60", "name": "p2_Target_Weight"},
    {"addr": "DB1520,REAL64", "name": "p2_TT_SP"},
    {"addr": "DB1520,REAL76", "name": "p2_Agitator_Speed"},
    {"addr": "DB1520,REAL80", "name": "p2_High_Shear_SP"},
    {"addr": "DB1520,INT84", "name": "p2_Step_Time_SP"},
    {"addr": "DB1520,X86.0", "name": "p2_Cmd_NewStep"},

    # Plant 3 Telemetry (DB1532)
    {"addr": "DB1532,INT0", "name": "p3_watchdog"},
    {"addr": "DB1532,INT2", "name": "p3_plc_state"},
    {"addr": "DB1532,INT4", "name": "p3_current_step"},
    {"addr": "DB1532,INT6", "name": "p3_step_timer"},
    {"addr": "DB1532,REAL8", "name": "p3_mix_temp"},
    {"addr": "DB1532,REAL12", "name": "p3_mix_weight"},
    {"addr": "DB1532,REAL16", "name": "p3_agitator_act"},
    {"addr": "DB1532,REAL20", "name": "p3_highshear_act"},
    {"addr": "DB1532,REAL24", "name": "p3_hopper_weight"},

    # Plant 3 Command (DB1530)
    {"addr": "DB1530,STRING0.20", "name": "p3_Batch_ID"},
    {"addr": "DB1530,INT22", "name": "p3_HMI_Command"},
    {"addr": "DB1530,INT24", "name": "p3_Step_ID"},
    {"addr": "DB1530,STRING26.10", "name": "p3_Phase_ID"},
    {"addr": "DB1530,STRING38.20", "name": "p3_Re_Code"},
    {"addr": "DB1530,REAL60", "name": "p3_Target_Weight"},
    {"addr": "DB1530,REAL64", "name": "p3_TT_SP"},
    {"addr": "DB1530,REAL76", "name": "p3_Agitator_Speed"},
    {"addr": "DB1530,REAL80", "name": "p3_High_Shear_SP"},
    {"addr": "DB1530,INT84", "name": "p3_Step_Time_SP"},
    {"addr": "DB1530,X86.0", "name": "p3_Cmd_NewStep"}
]
endpoint['vartable'] = vartable

# 3. Fix Plant 3 Write Function Node (uses p3_ prefix now)
for f in flows:
    if f.get('name') == 'Parse CMD -> DB1530':
        f['func'] = """const cmd = msg.payload;
const vars = [];
const vals = [];

if (cmd.Batch_ID !== undefined) { vars.push("p3_Batch_ID"); vals.push(String(cmd.Batch_ID)); }
if (cmd.Phase_ID !== undefined) { vars.push("p3_Phase_ID"); vals.push(String(cmd.Phase_ID)); }
if (cmd.Re_Code_ID !== undefined) { vars.push("p3_Re_Code"); vals.push(String(cmd.Re_Code_ID)); }
let reqQty = cmd.Req_Qty !== undefined ? cmd.Req_Qty : (cmd.Target_Weight !== undefined ? cmd.Target_Weight : cmd.require);
if (reqQty !== undefined && reqQty !== null) { vars.push("p3_Target_Weight"); vals.push(Number(reqQty)); }
if (cmd.HMI_Command !== undefined) { vars.push("p3_HMI_Command"); vals.push(Number(cmd.HMI_Command)); }
if (cmd.Step_ID !== undefined) { vars.push("p3_Step_ID"); vals.push(Number(cmd.Step_ID)); }
if (cmd.TT_SP !== undefined) { vars.push("p3_TT_SP"); vals.push(Number(cmd.TT_SP[0] || 0)); }
if (cmd.Agitator_Speed !== undefined) { vars.push("p3_Agitator_Speed"); vals.push(Number(cmd.Agitator_Speed)); }
if (cmd.High_Shear_SP !== undefined) { vars.push("p3_High_Shear_SP"); vals.push(Number(cmd.High_Shear_SP)); }
if (cmd.Step_Time_SP !== undefined) { vars.push("p3_Step_Time_SP"); vals.push(Number(cmd.Step_Time_SP)); }
if (cmd.Cmd_NewStep !== undefined) { vars.push("p3_Cmd_NewStep"); vals.push(Boolean(cmd.Cmd_NewStep)); }

msg.variable = vars;
msg.payload = vals;
return msg;"""
    if f.get('name') == 'Sub CMD Plant 3':
        broker_id_local = next(x['id'] for x in flows if x.get('type') == 'mqtt-broker' and x.get('name') == 'LOCAL')
        broker_id_remote = next(x['id'] for x in flows if x.get('type') == 'mqtt-broker' and x.get('name') == 'REMOTE')
        f['name'] = 'Sub CMD Plant 3 (Local)'
        f['broker'] = broker_id_local
        # Duplicate for remote broker
        remote_node = f.copy()
        remote_node['id'] = generate_id()
        remote_node['name'] = 'Sub CMD Plant 3 (Remote)'
        remote_node['broker'] = broker_id_remote
        remote_node['y'] += 40
        flows.append(remote_node)
# 4. Add Plant 1 Write Flow
broker_id_local = next(f['id'] for f in flows if f.get('type') == 'mqtt-broker' and f.get('name') == 'LOCAL')
broker_id_remote = next(f['id'] for f in flows if f.get('type') == 'mqtt-broker' and f.get('name') == 'REMOTE')

p1_mqtt_in_local = generate_id()
p1_mqtt_in_remote = generate_id()
p1_format = generate_id()
p1_s7_out = generate_id()

flows.extend([
    {
        "id": p1_mqtt_in_local,
        "type": "mqtt in",
        "z": tab_id,
        "name": "Sub CMD Plant 1 (Local)",
        "topic": "mixing/plant/1/step_cmd",
        "qos": "0",
        "datatype": "json",
        "broker": broker_id_local,
        "nl": False,
        "rap": True,
        "rh": 0,
        "inputs": 0,
        "x": 160,
        "y": 500,
        "wires": [[p1_format]]
    },
    {
        "id": p1_mqtt_in_remote,
        "type": "mqtt in",
        "z": tab_id,
        "name": "Sub CMD Plant 1 (Remote)",
        "topic": "mixing/plant/1/step_cmd",
        "qos": "0",
        "datatype": "json",
        "broker": broker_id_remote,
        "nl": False,
        "rap": True,
        "rh": 0,
        "inputs": 0,
        "x": 160,
        "y": 540,
        "wires": [[p1_format]]
    },
    {
        "id": p1_format,
        "type": "function",
        "z": tab_id,
        "name": "Parse CMD -> DB1510",
        "func": """const cmd = msg.payload;
const vars = [];
const vals = [];

if (cmd.Batch_ID !== undefined) { vars.push("p1_Batch_ID"); vals.push(String(cmd.Batch_ID)); }
if (cmd.Phase_ID !== undefined) { vars.push("p1_Phase_ID"); vals.push(String(cmd.Phase_ID)); }
if (cmd.Re_Code_ID !== undefined) { vars.push("p1_Re_Code"); vals.push(String(cmd.Re_Code_ID)); }
let reqQty = cmd.Req_Qty !== undefined ? cmd.Req_Qty : (cmd.Target_Weight !== undefined ? cmd.Target_Weight : cmd.require);
if (reqQty !== undefined && reqQty !== null) { vars.push("p1_Target_Weight"); vals.push(Number(reqQty)); }
if (cmd.HMI_Command !== undefined) { vars.push("p1_HMI_Command"); vals.push(Number(cmd.HMI_Command)); }
if (cmd.Step_ID !== undefined) { vars.push("p1_Step_ID"); vals.push(Number(cmd.Step_ID)); }
if (cmd.TT_SP !== undefined) { vars.push("p1_TT_SP"); vals.push(Number(cmd.TT_SP[0] || 0)); }
if (cmd.Agitator_Speed !== undefined) { vars.push("p1_Agitator_Speed"); vals.push(Number(cmd.Agitator_Speed)); }
if (cmd.High_Shear_SP !== undefined) { vars.push("p1_High_Shear_SP"); vals.push(Number(cmd.High_Shear_SP)); }
if (cmd.Step_Time_SP !== undefined) { vars.push("p1_Step_Time_SP"); vals.push(Number(cmd.Step_Time_SP)); }
if (cmd.Cmd_NewStep !== undefined) { vars.push("p1_Cmd_NewStep"); vals.push(Boolean(cmd.Cmd_NewStep)); }

msg.variable = vars;
msg.payload = vals;
return msg;""",
        "outputs": 1,
        "x": 380,
        "y": 500,
        "wires": [[p1_s7_out]]
    },
    {
        "id": p1_s7_out,
        "type": "s7 out",
        "z": tab_id,
        "endpoint": endpoint['id'],
        "variable": "",
        "name": "Write DB1510",
        "x": 620,
        "y": 500,
        "wires": []
    }
])

# 5. Add Plant 2 Telemetry (Read) Flow
p2_s7_in = generate_id()
p2_format = generate_id()
p2_mqtt_out = "mqtt_out_plant2"
flows.extend([
    {
        "id": p2_s7_in,
        "type": "s7 in",
        "z": tab_id,
        "endpoint": endpoint['id'],
        "mode": "all",
        "name": "Read PLC DB1522",
        "x": 160,
        "y": 240,
        "wires": [[p2_format]]
    },
    {
        "id": p2_format,
        "type": "function",
        "z": tab_id,
        "name": "Format Plant 2 Status",
        "func": """const plc = msg.payload;
msg.payload = {
    "Step_no": Number(plc.p2_current_step || 0),
    "Step_Timer": Number(plc.p2_step_timer || 0),
    "Mixing_Tank_Volume": Number(Number(plc.p2_mix_weight || 0).toFixed(2)),
    "Mixing_Tank_Temperature": Number(Number(plc.p2_mix_temp || 0).toFixed(2)),
    "MixingTank_Agitator_Speed": Number(Number(plc.p2_agitator_act || 0).toFixed(2)),
    "HighShare_Speed": Number(Number(plc.p2_highshear_act || 0).toFixed(2)),
    "watchdog": Number(plc.p2_watchdog || 0),
    "PLC_State": Number(plc.p2_plc_state || 0),
    "Hopper_Weight": Number(Number(plc.p2_hopper_weight || 0).toFixed(2))
};
return msg;""",
        "outputs": 1,
        "x": 380,
        "y": 240,
        "wires": [[p2_mqtt_out]]
    },
    {
        "id": p2_mqtt_out,
        "type": "mqtt out",
        "z": tab_id,
        "name": "Publish Plant 2",
        "topic": "/MIX-02",
        "qos": "0",
        "retain": "",
        "broker": broker_id,
        "x": 620,
        "y": 240,
        "wires": []
    }
])

# 6. Add Plant 2 Command (Write) Flow
p2_mqtt_in_local = generate_id()
p2_mqtt_in_remote = generate_id()
p2_format_cmd = generate_id()
p2_s7_out = generate_id()

flows.extend([
    {
        "id": p2_mqtt_in_local,
        "type": "mqtt in",
        "z": tab_id,
        "name": "Sub CMD Plant 2 (Local)",
        "topic": "mixing/plant/2/step_cmd",
        "qos": "0",
        "datatype": "json",
        "broker": broker_id_local,
        "nl": False,
        "rap": True,
        "rh": 0,
        "inputs": 0,
        "x": 160,
        "y": 600,
        "wires": [[p2_format_cmd]]
    },
    {
        "id": p2_mqtt_in_remote,
        "type": "mqtt in",
        "z": tab_id,
        "name": "Sub CMD Plant 2 (Remote)",
        "topic": "mixing/plant/2/step_cmd",
        "qos": "0",
        "datatype": "json",
        "broker": broker_id_remote,
        "nl": False,
        "rap": True,
        "rh": 0,
        "inputs": 0,
        "x": 160,
        "y": 640,
        "wires": [[p2_format_cmd]]
    },
    {
        "id": p2_format_cmd,
        "type": "function",
        "z": tab_id,
        "name": "Parse CMD -> DB1520",
        "func": """const cmd = msg.payload;
const vars = [];
const vals = [];

if (cmd.Batch_ID !== undefined) { vars.push("p2_Batch_ID"); vals.push(String(cmd.Batch_ID)); }
if (cmd.Phase_ID !== undefined) { vars.push("p2_Phase_ID"); vals.push(String(cmd.Phase_ID)); }
if (cmd.Re_Code_ID !== undefined) { vars.push("p2_Re_Code"); vals.push(String(cmd.Re_Code_ID)); }
let reqQty = cmd.Req_Qty !== undefined ? cmd.Req_Qty : (cmd.Target_Weight !== undefined ? cmd.Target_Weight : cmd.require);
if (reqQty !== undefined && reqQty !== null) { vars.push("p2_Target_Weight"); vals.push(Number(reqQty)); }
if (cmd.HMI_Command !== undefined) { vars.push("p2_HMI_Command"); vals.push(Number(cmd.HMI_Command)); }
if (cmd.Step_ID !== undefined) { vars.push("p2_Step_ID"); vals.push(Number(cmd.Step_ID)); }
if (cmd.TT_SP !== undefined) { vars.push("p2_TT_SP"); vals.push(Number(cmd.TT_SP[0] || 0)); }
if (cmd.Agitator_Speed !== undefined) { vars.push("p2_Agitator_Speed"); vals.push(Number(cmd.Agitator_Speed)); }
if (cmd.High_Shear_SP !== undefined) { vars.push("p2_High_Shear_SP"); vals.push(Number(cmd.High_Shear_SP)); }
if (cmd.Step_Time_SP !== undefined) { vars.push("p2_Step_Time_SP"); vals.push(Number(cmd.Step_Time_SP)); }
if (cmd.Cmd_NewStep !== undefined) { vars.push("p2_Cmd_NewStep"); vals.push(Boolean(cmd.Cmd_NewStep)); }

msg.variable = vars;
msg.payload = vals;
return msg;""",
        "outputs": 1,
        "x": 380,
        "y": 600,
        "wires": [[p2_s7_out]]
    },
    {
        "id": p2_s7_out,
        "type": "s7 out",
        "z": tab_id,
        "endpoint": endpoint['id'],
        "variable": "",
        "name": "Write DB1520",
        "x": 620,
        "y": 600,
        "wires": []
    }
])
# 7. Fix telemetry format nodes to prevent flickering
for f in flows:
    name = f.get('name')
    if name in ['Format Plant 1 Status', 'Format Plant 2 Status', 'Format Plant 3 Status']:
        f['func'] = "return null;"

with open('final_flows.json', 'w') as f:
    json.dump(flows, f, indent=4)
