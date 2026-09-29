import urllib.request
import json
import uuid

def generate_id():
    return uuid.uuid4().hex[:16]

def run():
    # 1. Get current flows
    req = urllib.request.Request("http://127.0.0.1:1880/flows", method="GET")
    try:
        with urllib.request.urlopen(req) as response:
            flows = json.loads(response.read().decode())
    except Exception as e:
        print(f"Error fetching flows: {e}")
        return

    # 2. Find necessary components
    try:
        # Assuming the first tab is the one we want if we can't find 'Monitor'
        tabs = [f for f in flows if f.get('type') == 'tab']
        monitor_tabs = [t for t in tabs if 'Monitor' in t.get('label', '')]
        tab_id = monitor_tabs[0]['id'] if monitor_tabs else tabs[0]['id']
        
        broker = next((f for f in flows if f.get('type') == 'mqtt-broker' and f.get('name') == 'LOCAL'), None)
        if not broker:
            broker = next((f for f in flows if f.get('type') == 'mqtt-broker'), None)
        broker_id_local = broker['id']
        
        endpoint = next(f for f in flows if f.get('type') == 's7 endpoint' and f.get('name') == 'Siemens_S7-1200')
    except StopIteration as e:
        print("Could not find necessary nodes (tab, broker, or S7 endpoint)")
        return

    # 3. Add flows for Plant 1, 2, 3
    y_offset = 1000
    
    # We will create 3 sets of flows
    for plant_id in [1, 2, 3]:
        mqtt_in = generate_id()
        debug_node = generate_id()
        func_node = generate_id()
        s7_out = generate_id()
        
        topic = f"MPL/PLC/Plant{plant_id}/Recipe_Sync"
        db_var = f"DB15{plant_id}1,B0"
        
        new_nodes = [
            {
                "id": mqtt_in,
                "type": "mqtt in",
                "z": tab_id,
                "name": f"Sub Recipe Plant {plant_id}",
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
                "wires": [[func_node, debug_node]]
            },
            {
                "id": debug_node,
                "type": "debug",
                "z": tab_id,
                "name": f"Debug P{plant_id} Recipe",
                "active": True,
                "tosidebar": True,
                "console": False,
                "tostatus": False,
                "complete": "payload",
                "targetType": "msg",
                "statusVal": "",
                "statusType": "auto",
                "x": 420,
                "y": y_offset - 40,
                "wires": []
            },
            {
                "id": func_node,
                "type": "function",
                "z": tab_id,
                "name": f"Parse -> {db_var}",
                "func": f"""let buf = Buffer.alloc(10036);
buf.fill(0);

function writeS7String(buffer, offset, str, maxLen) {{
    buffer.writeUInt8(maxLen, offset);
    if (!str) str = "";
    let strBuf = Buffer.from(str, 'utf8');
    let actualLen = Math.min(strBuf.length, maxLen);
    buffer.writeUInt8(actualLen, offset + 1);
    strBuf.copy(buffer, offset + 2, 0, actualLen);
}}

let data = msg.payload;
if (!data || !data.steps) return null;

// Header (52 bytes)
writeS7String(buf, 0, data.batch_id, 20);
writeS7String(buf, 22, data.sku_id, 20);
buf.writeInt16BE(1, 44);
buf.writeInt16BE(data.total_steps || 0, 46);
buf.writeInt16BE(1, 48);
buf.writeUInt8(1, 50);

// Steps (Max 128)
let steps = data.steps || [];
for(let i=0; i<Math.min(steps.length, 128); i++) {{
    let step = steps[i];
    let offset = 52 + (i * 78);
    
    buf.writeInt16BE(step.seq || 0, offset + 0);
    buf.writeInt16BE(step.phase_no || 0, offset + 2);
    buf.writeInt16BE(step.sub_step || 0, offset + 4);
    
    writeS7String(buf, offset + 6, step.action_code || "", 10);
    writeS7String(buf, offset + 18, step.phase_id || "", 10);
    writeS7String(buf, offset + 30, step.re_code || "", 20);
    
    buf.writeFloatBE(step.target_weight || 0.0, offset + 52);
    buf.writeFloatBE(step.temp_sp || 0.0, offset + 56);
    buf.writeFloatBE(step.temp_low || 0.0, offset + 60);
    buf.writeFloatBE(step.temp_high || 0.0, offset + 64);
    buf.writeFloatBE(step.agitator_sp || 0.0, offset + 68);
    buf.writeFloatBE(step.highshear_sp || 0.0, offset + 72);
    buf.writeInt16BE(step.step_time || 0, offset + 76);
}}

msg.payload = buf;
msg.variable = "{db_var}";
return msg;""",
                "outputs": 1,
                "x": 420,
                "y": y_offset + 20,
                "wires": [[s7_out]]
            },
            {
                "id": s7_out,
                "type": "s7 out",
                "z": tab_id,
                "endpoint": endpoint['id'],
                "variable": "",
                "name": f"Write {db_var}",
                "x": 700,
                "y": y_offset + 20,
                "wires": []
            }
        ]
        
        flows.extend(new_nodes)
        y_offset += 150

    # 4. POST updated flows back to Node-RED
    data = json.dumps(flows).encode('utf-8')
    req = urllib.request.Request("http://127.0.0.1:1880/flows", data=data, headers={'Content-Type': 'application/json', 'Node-RED-Deployment-Type': 'full'})
    try:
        with urllib.request.urlopen(req) as response:
            print("Successfully updated Node-RED flows!")
    except Exception as e:
        print(f"Error updating flows: {e}")

if __name__ == '__main__':
    run()
