from plc_service import plc
plc.connect()
for db in [1512, 1522, 1532]:
    try:
        data = plc.db_read(db, 0, 36)
        print(f"DB{db} exists: {data is not None}")
    except Exception as e:
        print(f"DB{db} error: {e}")
