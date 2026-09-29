from plc_service import plc
plc.connect()
print("DB1511 read:", plc.db_read(1511, 0, 10))
print("DB1521 read:", plc.db_read(1521, 0, 10))
print("DB1531 read:", plc.db_read(1531, 0, 10))
