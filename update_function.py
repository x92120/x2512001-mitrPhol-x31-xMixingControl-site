import json, requests

with open('final_flows.json', 'r') as f:
    flows = json.load(f)

for f in flows:
    if f.get('type') == 'function' and f.get('name', '').startswith('Parse Telemetry -> DB15'):
        plant_id = f['name'][-2] # e.g. "1" from "DB1512"
        var_prefix = f"p{plant_id}"
        f['func'] = f"""let act = msg.payload;

// Handle Buffer (sometimes MQTT payloads are Buffers)
if (Buffer.isBuffer(act)) {{
    try {{ act = act.toString('utf8'); }} catch(e) {{}}
}}

// Handle String
if (typeof act === "string") {{
    try {{ act = JSON.parse(act); }} catch(e) {{}}
}}

// Handle Array (if the payload is like [{{watchdog: 1}}])
if (Array.isArray(act) && act.length > 0) {{
    act = act[0];
}}

// Handle Wrapper (if payload is like {{"MIX-01": {{...}} }})
if (act && act["MIX-0{plant_id}"]) {{ act = act["MIX-0{plant_id}"]; }}

const vars = [];
const vals = [];

if (act && act.watchdog !== undefined) {{ vars.push("{var_prefix}_watchdog"); vals.push(Number(act.watchdog)); }}
if (act && act.PLC_State !== undefined) {{ vars.push("{var_prefix}_plc_state"); vals.push(Number(act.PLC_State)); }}
if (act && (act.Current_Step !== undefined || act.Step_no !== undefined)) {{ vars.push("{var_prefix}_current_step"); vals.push(Number(act.Current_Step || act.Step_no || 0)); }}
if (act && act.Step_Timer !== undefined) {{ vars.push("{var_prefix}_step_timer"); vals.push(Number(act.Step_Timer)); }}
if (act && (act.MixTank_Temp !== undefined || act.Mixing_Tank_Temperature !== undefined)) {{ vars.push("{var_prefix}_mix_temp"); vals.push(Number(act.MixTank_Temp || act.Mixing_Tank_Temperature || 0)); }}
if (act && (act.MixTank_Weight !== undefined || act.Mixing_Tank_Volume !== undefined || act.Scale_Act !== undefined)) {{ vars.push("{var_prefix}_mix_weight"); vals.push(Number(act.MixTank_Weight || act.Mixing_Tank_Volume || act.Scale_Act || 0)); }}
if (act && (act.Agitator_Act !== undefined || act.MixingTank_Agitator_Speed !== undefined)) {{ vars.push("{var_prefix}_agitator_act"); vals.push(Number(act.Agitator_Act || act.MixingTank_Agitator_Speed || 0)); }}
if (act && (act.HighShear_Act !== undefined || act.HighShare_Speed !== undefined)) {{ vars.push("{var_prefix}_highshear_act"); vals.push(Number(act.HighShear_Act || act.HighShare_Speed || 0)); }}
if (act && act.Hopper_Weight !== undefined) {{ vars.push("{var_prefix}_hopper_weight"); vals.push(Number(act.Hopper_Weight)); }}

msg.variable = vars;
msg.payload = vals;

// Debugging
if (vars.length === 0) {{
    node.warn("No matching variables found. Raw payload: " + JSON.stringify(msg.payload) + " | Parsed act: " + JSON.stringify(act));
}}

return msg;"""

with open('final_flows.json', 'w') as f:
    json.dump(flows, f, indent=4)

r = requests.post('http://localhost:1880/flows', json=flows)
print("Deploy status:", r.status_code)
