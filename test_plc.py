import sys
sys.path.append('/home/x-root/xApp/x2512001-mitrPhol-x31-xMixingControl/x3101-app/x3101-0210-backEnd/x0201-fastAPI')
from plc_service import read_telemetry

for i in [1, 2, 3]:
    data = read_telemetry(i)
    if data:
        print(f"Plant {i}:")
        print(f"  Step: {data.get('current_step')} Timer: {data.get('step_timer')}")
        print(f"  MixTemp: {data.get('mix_temp')} MixWeight: {data.get('mix_weight')}")
        print(f"  Agitator: {data.get('agitator_act')} Hopper: {data.get('hopper_weight')}")
    else:
        print(f"Plant {i} failed to read")
