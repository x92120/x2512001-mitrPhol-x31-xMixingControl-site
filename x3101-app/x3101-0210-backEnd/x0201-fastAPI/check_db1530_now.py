from plc_service import plc
import struct
plc.connect()
data = plc.db_read(1530, 0, 88)
hmi_cmd = struct.unpack_from(">h", data, 22)[0]
step_id = struct.unpack_from(">h", data, 24)[0]
new_step = bool(data[86] & 0x01)
print(f"HMI_Command: {hmi_cmd}, Step_ID: {step_id}, Cmd_NewStep: {new_step}")
