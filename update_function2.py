import json, requests

with open('final_flows.json', 'r') as f:
    flows = json.load(f)

for f in flows:
    if f.get('type') == 'function' and f.get('name', '').startswith('Parse Telemetry -> DB15'):
        plant_id = f['name'][-2] # e.g. "1" from "DB1512"
        var_prefix = f"p{plant_id}"
        f['func'] = f"""let act = msg.payload;

if (Buffer.isBuffer(act)) {{
    try {{ act = act.toString('utf8'); }} catch(e) {{}}
}}

if (typeof act === "string") {{
    try {{ act = JSON.parse(act); }} catch(e) {{}}
}}

if (Array.isArray(act) && act.length > 0) {{
    act = act[0];
}}

// Support unwrapping if it's nested like {{"MIX-01": {{...}} }}
if (act && act["MIX-0{plant_id}"]) {{ act = act["MIX-0{plant_id}"]; }}

const vars = [];
const vals = [];

// Helper function to safely get values from keys with prefix MIX0X. 
function getValue(keys) {{
    if (!act) return undefined;
    for (let i = 0; i < keys.length; i++) {{
        if (act[keys[i]] !== undefined) return act[keys[i]];
        if (act[`MIX0{plant_id}.${{keys[i]}}`] !== undefined) return act[`MIX0{plant_id}.${{keys[i]}}`];
    }}
    return undefined;
}}

let watchdog = getValue(["watchdog", "Watch_Doc", "WATCHDOG"]);
if (watchdog !== undefined) {{ vars.push("{var_prefix}_watchdog"); vals.push(Number(watchdog)); }}

let plc_state = getValue(["PLC_State", "PLC_STATE"]);
if (plc_state !== undefined) {{ vars.push("{var_prefix}_plc_state"); vals.push(Number(plc_state)); }}

let current_step = getValue(["Current_Step", "Step_no"]);
if (current_step !== undefined) {{ vars.push("{var_prefix}_current_step"); vals.push(Number(current_step)); }}

let step_timer = getValue(["Step_Timer"]);
if (step_timer !== undefined) {{ vars.push("{var_prefix}_step_timer"); vals.push(Number(step_timer)); }}

let mix_temp = getValue(["MixTank_Temp", "Mixing_Tank_Temperature", "Temp_Act"]);
if (mix_temp !== undefined) {{ vars.push("{var_prefix}_mix_temp"); vals.push(Number(mix_temp)); }}

let mix_weight = getValue(["MixTank_Weight", "Mixing_Tank_Volume", "Scale_Act"]);
if (mix_weight !== undefined) {{ vars.push("{var_prefix}_mix_weight"); vals.push(Number(mix_weight)); }}

let agitator_act = getValue(["Agitator_Act", "MixingTank_Agitator_Speed"]);
if (agitator_act !== undefined) {{ vars.push("{var_prefix}_agitator_act"); vals.push(Number(agitator_act)); }}

let highshear_act = getValue(["HighShear_Act", "HighShare_Speed"]);
if (highshear_act !== undefined) {{ vars.push("{var_prefix}_highshear_act"); vals.push(Number(highshear_act)); }}

let hopper_weight = getValue(["Hopper_Weight"]);
if (hopper_weight !== undefined) {{ vars.push("{var_prefix}_hopper_weight"); vals.push(Number(hopper_weight)); }}

msg.variable = vars;
msg.payload = vals;

if (vars.length === 0) {{
    node.warn("No matching variables found. Parsed act: " + JSON.stringify(act));
}}

return msg;"""

with open('final_flows.json', 'w') as f:
    json.dump(flows, f, indent=4)

r = requests.post('http://localhost:1880/flows', json=flows)
print("Deploy status:", r.status_code)
