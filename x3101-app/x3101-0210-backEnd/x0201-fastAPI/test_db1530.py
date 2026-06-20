from plc_service import plc
plc.connect()
try:
    d = plc.db_read(1530, 0, 4)
    print("DB1530 exists")
except Exception as e:
    print(f"DB1530 error: {e}")
