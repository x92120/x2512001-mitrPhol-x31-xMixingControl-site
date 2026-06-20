import json

with open('new_flows.json', 'r') as f:
    flows = json.load(f)

for f in flows:
    if f.get('name') == 'Format Plant 3 Status':
        f['func'] = """const plc = msg.payload;
msg.payload = {
    "Step_no": Number(plc.p3_current_step || 0),
    "Step_Timer": Number(plc.p3_step_timer || 0),
    "Mixing_Tank_Volume": Number(Number(plc.p3_mix_weight || 0).toFixed(2)),
    "Mixing_Tank_Temperature": Number(Number(plc.p3_mix_temp || 0).toFixed(2)),
    "MixingTank_Agitator_Speed": Number(Number(plc.p3_agitator_act || 0).toFixed(2)),
    "HighShare_Speed": Number(Number(plc.p3_highshear_act || 0).toFixed(2)),
    "watchdog": Number(plc.p3_watchdog || 0),
    "PLC_State": Number(plc.p3_plc_state || 0),
    "Hopper_Weight": Number(Number(plc.p3_hopper_weight || 0).toFixed(2))
};
return msg;"""

with open('new_flows.json', 'w') as f:
    json.dump(flows, f, indent=4)
