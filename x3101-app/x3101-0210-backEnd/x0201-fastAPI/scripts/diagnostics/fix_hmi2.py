import struct
import snap7

plc = snap7.client.Client()
plc.connect('192.168.21.210', 0, 1)

# Restore offset 44
plc.db_write(1510, 44, struct.pack('>h', 24948))
plc.db_write(1520, 44, struct.pack('>h', 20302))

# Write HMI_Command = 1 to offset 22
plc.db_write(1510, 22, struct.pack('>h', 1))
plc.db_write(1520, 22, struct.pack('>h', 1))

plc.disconnect()
print("Done")
