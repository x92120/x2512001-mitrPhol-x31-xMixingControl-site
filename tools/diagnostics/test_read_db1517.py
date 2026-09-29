import struct
import sys
sys.path.append('/home/x-root/xApp/x2512001-mitrPhol-x31-xMixingControl/x3101-app/x3120-plcBackend')
from plc_service import plc

plc.connect()
if not plc.is_connected:
    print("Could not connect to PLC")
    sys.exit(1)

data = plc.db_read(1517, 0, 50)
if data:
    print("Successfully read header from DB1517")
    print(data.hex())
else:
    print("Failed to read DB1517")
