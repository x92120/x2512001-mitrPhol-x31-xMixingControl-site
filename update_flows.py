import json
import copy

with open('current_flows.json', 'r') as f:
    flows = json.load(f)

# 1. Update s7_plc_endpoint with DB1532 and DB1530 variables
endpoint = next(n for n in flows if n['id'] == 's7_plc_endpoint')

# Add DB1532 vars
p3_telemetry = [
    {"addr": "DB1532,INT0", "name": "p3_watchdog"},
    {"addr": "DB1532,INT2", "name": "p3_plc_state"},
    {"addr": "DB1532,INT4", "name": "p3_current_step"},
    {"addr": "DB1532,INT6", "name": "p3_step_timer"},
    {"addr": "DB1532,REAL8", "name": "p3_mix_temp"},
    {"addr": "DB1532,REAL12", "name": "p3_mix_weight"},
    {"addr": "DB1532,REAL16", "name": "p3_agitator_act"},
    {"addr": "DB1532,REAL20", "name": "p3_highshear_act"},
]

# Add DB1530 vars for write
p3_cmd = [
    {"addr": "DB1530,INT0", "name": "cmd_step_no"},
    {"addr": "DB1530,INT2", "name": "cmd_action_code"},
    {"addr": "DB1530,REAL4", "name": "cmd_target_weight"},
    {"addr": "DB1530,REAL8", "name": "cmd_temp_sp"},
    {"addr": "DB1530,REAL12", "name": "cmd_temp_low"},
    {"addr": "DB1530,REAL16", "name": "cmd_temp_high"},
    {"addr": "DB1530,REAL20", "name": "cmd_agitator_sp"},
    {"addr": "DB1530,REAL24", "name": "cmd_highshear_sp"},
    {"addr": "DB1530,INT28", "name": "cmd_step_time"},
    {"addr": "DB1530,REAL30", "name": "cmd_low_tol"},
    {"addr": "DB1530,REAL34", "name": "cmd_high_tol"},
    {"addr": "DB1530,X86.0", "name": "cmd_newstep"}  # Assuming Cmd_NewStep is at 86.0, wait, I need to check DB1530 structure!
]

# Wait, the user said "คำสั่งเข้า DB1530". How is DB1530 structured?
# If DB100 was:
# DB100.0 INT Step Number
# DB100.2 INT Action Code
# DB100.4 REAL Target Weight
# ...
# DB100.28 INT Step Time
# DB100.30 REAL Low Tolerance
# DB100.34 REAL High Tolerance
# HMI_Command is DB100.82 ? Wait, in x61-MixingControl.vue, it sends JSON.

# Let's just create a dynamic S7 Out node using the "s7 control" or something?
# No, "s7 out" in node-red-contrib-s7 uses `msg.variable` to write to a specific variable, OR if `msg.payload` is an object, it writes multiple.
