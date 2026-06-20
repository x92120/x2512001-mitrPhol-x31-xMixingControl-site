from plc_service import plc
import struct
plc.connect()

data1 = plc.db_read(1510, 0, 88)
if data1:
    hmi_cmd1 = struct.unpack_from(">h", data1, 22)[0]
    step_id1 = struct.unpack_from(">h", data1, 24)[0]
    print(f"Plant 1 (DB1510) - HMI_Command: {hmi_cmd1}, Step_ID: {step_id1}")

data2 = plc.db_read(1520, 0, 88)
if data2:
    hmi_cmd2 = struct.unpack_from(">h", data2, 22)[0]
    step_id2 = struct.unpack_from(">h", data2, 24)[0]
    print(f"Plant 2 (DB1520) - HMI_Command: {hmi_cmd2}, Step_ID: {step_id2}")
