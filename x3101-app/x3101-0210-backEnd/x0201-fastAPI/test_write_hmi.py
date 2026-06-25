"""
Quick diagnostic: Test writing hmi_command to DB1510 at BOTH offsets (+22 and +44)
and then read back to verify which one is actually writable by the app.

Usage:
    cd /home/x-root/xApp/x2512001-mitrPhol-x31-xMixingControl/x3101-app/x3101-0210-backEnd/x0201-fastAPI
    source venv/bin/activate
    python test_write_hmi.py [value=2] [plant=1]

Example - set PAUSE (hmi=2) on plant 1:
    python test_write_hmi.py 2 1

Example - set START (hmi=1) on plant 1:
    python test_write_hmi.py 1 1
"""

import struct
import sys
import time
from plc_service import plc, get_db_number

hmi_val = int(sys.argv[1]) if len(sys.argv) > 1 else 2
plant_id = int(sys.argv[2]) if len(sys.argv) > 2 else 1

db1510 = get_db_number('step_cmd', plant_id)   # 1510, 1520, or 1530
db1511 = get_db_number('full_recipe', plant_id) # 1511, 1521, or 1531

print(f"🔧 Writing hmi_command={hmi_val} to Plant {plant_id}")
print(f"   DB step_cmd:   DB{db1510}")
print(f"   DB full_recipe: DB{db1511}")

plc.connect()
if not plc.is_connected:
    print("❌ Cannot connect to PLC")
    exit(1)

print("✅ Connected")

# ── Read BEFORE ──
d10 = plc.db_read(db1510, 0, 50)
d11 = plc.db_read(db1511, 0, 52)

def read_int(data, offset):
    if data and offset + 2 <= len(data):
        return struct.unpack_from('>h', data, offset)[0]
    return None

print(f"\n  BEFORE DB{db1510}:")
print(f"    +0  = {read_int(d10,  0)}   (Batch_ID first 2 bytes as Int)")
print(f"    +22 = {read_int(d10, 22)}   ← HMI_Command candidate A")
print(f"    +44 = {read_int(d10, 44)}   ← HMI_Command candidate B")

print(f"\n  BEFORE DB{db1511}:")
print(f"    +44 = {read_int(d11, 44)}   ← HMI_Command in full_recipe")

# ── Write ──
print(f"\n  Writing hmi_command={hmi_val} to:")
print(f"    DB{db1511} offset +44 ...")
ok1 = plc.db_write(db1511, 44, struct.pack('>h', hmi_val))
print(f"    → {'OK' if ok1 else 'FAIL'}")

print(f"    DB{db1510} offset +22 ...")
ok2 = plc.db_write(db1510, 22, struct.pack('>h', hmi_val))
print(f"    → {'OK' if ok2 else 'FAIL'}")

time.sleep(0.3)

# ── Read AFTER ──
d10 = plc.db_read(db1510, 0, 50)
d11 = plc.db_read(db1511, 0, 52)

print(f"\n  AFTER DB{db1510}:")
v_after_22 = read_int(d10, 22)
v_after_44_10 = read_int(d10, 44)
print(f"    +22 = {v_after_22}   (expected {hmi_val} if offset is correct)")
print(f"    +44 = {v_after_44_10}")

print(f"\n  AFTER DB{db1511}:")
v_after_44_11 = read_int(d11, 44)
print(f"    +44 = {v_after_44_11}   (expected {hmi_val} if write OK)")

# ── Conclusion ──
print()
if v_after_44_11 == hmi_val:
    print(f"  ✅ DB{db1511}+44 = {hmi_val} → full_recipe HMI_Command updated correctly")
else:
    print(f"  ❌ DB{db1511}+44 = {v_after_44_11} (expected {hmi_val}) → full_recipe write FAILED!")

if v_after_22 == hmi_val:
    print(f"  ✅ DB{db1510}+22 = {hmi_val} → step_cmd HMI_Command offset +22 is CORRECT")
else:
    print(f"  ❌ DB{db1510}+22 = {v_after_22} (expected {hmi_val}) → offset +22 is WRONG")

plc.disconnect()
print("\nDone.")
