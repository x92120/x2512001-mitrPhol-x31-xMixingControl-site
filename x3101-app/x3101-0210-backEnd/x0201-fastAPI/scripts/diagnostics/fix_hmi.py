import struct
import snap7

plc = snap7.client.Client()
plc.connect('192.168.21.210', 0, 1)

# Plant 1
data = plc.db_read(1510, 44, 2)
print("Before Plant 1:", struct.unpack('>h', data)[0])
plc.db_write(1510, 44, struct.pack('>h', 1))

# Plant 2 (in case it is also stuck)
data = plc.db_read(1520, 44, 2)
print("Before Plant 2:", struct.unpack('>h', data)[0])
plc.db_write(1520, 44, struct.pack('>h', 1))

plc.disconnect()
print("Done")
