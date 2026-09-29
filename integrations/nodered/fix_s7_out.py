import json

with open('new_flows.json', 'r') as f:
    flows = json.load(f)

for f in flows:
    if f.get('name') == 'Parse CMD -> DB1530':
        f['func'] = """const cmd = msg.payload;
const msgs = [];
if (cmd.HMI_Command !== undefined) msgs.push({ payload: Number(cmd.HMI_Command), variable: "HMI_Command" });
if (cmd.Step_ID !== undefined) msgs.push({ payload: Number(cmd.Step_ID), variable: "Step_ID" });
if (cmd.TT_SP !== undefined) msgs.push({ payload: Number(cmd.TT_SP[0] || 0), variable: "TT_SP" });
if (cmd.Agitator_Speed !== undefined) msgs.push({ payload: Number(cmd.Agitator_Speed), variable: "Agitator_Speed" });
if (cmd.High_Shear_SP !== undefined) msgs.push({ payload: Number(cmd.High_Shear_SP), variable: "High_Shear_SP" });
if (cmd.Step_Time_SP !== undefined) msgs.push({ payload: Number(cmd.Step_Time_SP), variable: "Step_Time_SP" });
if (cmd.Cmd_NewStep !== undefined) msgs.push({ payload: Boolean(cmd.Cmd_NewStep), variable: "Cmd_NewStep" });
return [msgs];"""

with open('new_flows.json', 'w') as f:
    json.dump(flows, f, indent=4)
