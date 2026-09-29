"""
Debug: Dump raw bytes of DB1510/DB1520 (step_cmd) to find actual HMI_Command offset.
Run this script while the frontend is connected and sending PUT heartbeat (hmi_command=1 or 2).
Compare the bytes before and after to find which offset changes.

Usage:
    cd /home/x-root/xApp/x2512001-mitrPhol-x31-xMixingControl/x3101-app/x3101-0210-backEnd/x0201-fastAPI
    source venv/bin/activate
    python debug_db1510_raw.py
"""

import struct
import time
from plc_service import plc

plc.connect()
if not plc.is_connected:
    print("❌ Cannot connect to PLC")
    exit(1)

print("✅ Connected to PLC")
print()

def dump_db(db_num: int, size: int = 100):
    data = plc.db_read(db_num, 0, size)
    if data is None:
        print(f"  ❌ Failed to read DB{db_num}")
        return
    
    print(f"  DB{db_num} raw ({size} bytes):")
    # Print hex dump, 16 bytes per line
    for i in range(0, len(data), 16):
        chunk = data[i:i+16]
        hex_part = ' '.join(f'{b:02X}' for b in chunk)
        asc_part = ''.join(chr(b) if 32 <= b < 127 else '.' for b in chunk)
        print(f"    +{i:03d}: {hex_part:<48}  {asc_part}")
    print()
    
    # Parse Int(2) values at key offsets
    print(f"  DB{db_num} Int16 at offsets:")
    for offset in [0, 2, 22, 24, 44, 46]:
        if offset + 2 <= len(data):
            val = struct.unpack_from('>h', data, offset)[0]
            print(f"    offset+{offset:3d} = {val:6d}   (hex: {data[offset]:02X}{data[offset+1]:02X})")
    print()

for db in [1510, 1520]:
    print(f"{'='*60}")
    print(f"  Checking DB{db} (Plant {'1' if db == 1510 else '2'} step_cmd):")
    dump_db(db, 100)

print()
print("=== WRITE TEST ===")
print("Writing hmi_command=99 (test value) to DB1510 at offset+22...")
plc.db_write(1510, 22, struct.pack('>h', 99))
time.sleep(0.5)

data = plc.db_read(1510, 0, 100)
if data:
    val_at_22 = struct.unpack_from('>h', data, 22)[0]
    val_at_0  = struct.unpack_from('>h', data, 0)[0]
    val_at_44 = struct.unpack_from('>h', data, 44)[0]
    print(f"  After write to +22:")
    print(f"    offset+0  = {val_at_0}  (should be unchanged)")
    print(f"    offset+22 = {val_at_22} (should be 99 if correct offset)")
    print(f"    offset+44 = {val_at_44} (should be unchanged)")
    
    if val_at_22 == 99:
        print("  ✅ CONFIRMED: HMI_Command is at offset +22")
    else:
        print("  ❌ offset +22 did NOT change to 99 — wrong DB or wrong offset!")

print()
print("Writing hmi_command=1 to DB1510 at offset+22 (restore)...")
plc.db_write(1510, 22, struct.pack('>h', 1))
time.sleep(0.5)

# Final state
print()
print("=== FINAL STATE (after restore) ===")
for db in [1510, 1520]:
    dump_db(db, 50)

plc.disconnect()
print("Done.")
