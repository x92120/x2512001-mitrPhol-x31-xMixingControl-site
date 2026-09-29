from plc_service import plc
plc.connect()
for db in [1511, 1512, 1513]:
    try:
        data = plc.db_read(db, 0, 24)
        print(f"DB{db}: {data.hex() if data else None}")
    except Exception as e:
        print(f"DB{db} error: {e}")
