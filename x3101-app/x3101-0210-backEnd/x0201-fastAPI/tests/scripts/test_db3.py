from plc_service import plc
plc.connect()
for db in [1511, 1512, 1513, 1521, 1531, 1537]:
    try:
        data = plc.db_read(db, 0, 4)
        print(f"DB{db} exists: {data is not None}")
    except Exception as e:
        print(f"DB{db} error: {e}")
