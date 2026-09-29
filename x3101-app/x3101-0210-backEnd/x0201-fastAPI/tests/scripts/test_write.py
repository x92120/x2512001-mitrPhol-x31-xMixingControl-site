from plc_service import plc
import struct
plc.connect()
payload = b"\x00" * 130
print("DB1511 write:", plc.db_write(1511, 0, payload))
print("DB1521 write:", plc.db_write(1521, 0, payload))
print("DB1531 write:", plc.db_write(1531, 0, payload))
