import sys
sys.path.append('/home/x-root/xApp/x2512001-mitrPhol-x31-xMixingControl/x3101-app/x3101-0210-backEnd/x0201-fastAPI')
from plc_service import read_telemetry
import json
print(json.dumps(read_telemetry(1)))
