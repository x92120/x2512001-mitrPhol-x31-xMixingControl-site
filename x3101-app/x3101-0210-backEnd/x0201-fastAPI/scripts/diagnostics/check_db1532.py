from plc_service import plc
import time
plc.connect()
d1 = plc.db_read(1532, 0, 36)
time.sleep(2)
d2 = plc.db_read(1532, 0, 36)
if d1 and d2:
    for i in range(len(d1)):
        if d1[i] != d2[i]:
            print(f"Byte {i} changed: {d1[i]} -> {d2[i]}")
else:
    print("Failed to read")
