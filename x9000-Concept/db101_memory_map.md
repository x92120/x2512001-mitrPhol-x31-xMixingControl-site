# 🧠 DB1511 Memory Map (S7-1200 Non-Optimized)

This document maps the exact byte offsets for **DB1511 (DB_FULL_RECIPE)**. This is extremely important for writing your `python-snap7` `serialize()` function, as you must pack the binary payload to match these exact byte locations.

> **Important:** This assumes the DB is set to `S7_Optimized_Access := 'FALSE'` (Standard Access) so offsets are deterministic.

## 📦 1. `type_FullRecipe` (Header & Array)

This is the top-level structure of DB1511. The header takes up the first 52 bytes, followed by the array of 128 steps.

| Offset | Name | Data Type | Size (Bytes) | Description |
|---|---|---|---|---|
| `+0.0` | `Batch_ID` | String[20] | 22 | Batch Code (e.g. "P260411-02"). S7 strings have 2 header bytes. |
| `+22.0` | `SKU_ID` | String[20] | 22 | Recipe/SKU Code |
| `+44.0` | `HMI_Command` | Int | 2 | 0=IDLE, 1=START, 2=PAUSE, 3=ABORT, 9=RESET |
| `+46.0` | `Total_Steps` | Int | 2 | How many steps are actually populated (1-128) |
| `+48.0` | `Active_Step` | Int | 2 | PLC Pointer — current Seq number (1-128) |
| `+50.0` | `Cmd_LoadRecipe` | Bool | 1 (bit 0) | Trigger bit to tell PLC a new array is ready |
| *padding* | *(Padding)* | *(Byte)* | 1 | S7 aligns Arrays to even byte boundaries |
| `+52.0` | `Steps[1]` | type_RecipeStep | 78 | First step (See Table 2) |
| `+130.0` | `Steps[2]` | type_RecipeStep | 78 | Second step |
| `+208.0` | `Steps[3]` | type_RecipeStep | 78 | Third step |
| ... | ... | ... | 78 | ... repeats ... |
| `+9958.0` | `Steps[128]` | type_RecipeStep | 78 | Last step |

*(Total Size of DB1511: **10,036 bytes** ≈ 10 KB)*

---

## 🛠️ 2. `type_RecipeStep` (Individual Step Structure)

Each element in the `Steps[1..128]` array is exactly **78 bytes** long.

| Relative Offset | Name | Data Type | Size (Bytes) | Description |
|---|---|---|---|---|
| `+0.0` | `Seq` | Int | 2 | Flat sequence number (1, 2, 3, ... 128) |
| `+2.0` | `Phase_No` | Int | 2 | Phase number (10, 20, 30...) |
| `+4.0` | `Sub_Step` | Int | 2 | Step within phase (10, 20, 30...) |
| `+6.0` | `Action_Code` | String[10] | 12 | Action code (e.g. "x10010") |
| `+18.0` | `Phase_ID` | String[10] | 12 | Phase ID (e.g. "p0010") |
| `+30.0` | `Re_Code` | String[20] | 22 | Ingredient / Material code |
| `+52.0` | `Target_Weight` | Real | 4 | Target dosing weight (kg) |
| `+56.0` | `Temp_SP` | Real | 4 | Temperature setpoint (°C) |
| `+60.0` | `Temp_Low` | Real | 4 | Min temperature limit (°C) |
| `+64.0` | `Temp_High` | Real | 4 | Max temperature limit (°C) |
| `+68.0` | `Agitator_SP` | Real | 4 | Agitator speed (RPM) |
| `+72.0` | `HighShear_SP` | Real | 4 | High shear speed (RPM) |
| `+76.0` | `Step_Time` | Int | 2 | Hold time (Seconds) |

*(Total Size per Step: **78 bytes**)*

---

## 📋 3. Example: Cafe Amazon (S77S743200) — Flattened into Array

This is how the database recipe for SKU "Cafe Amazon" would be flattened into the `Steps[1..128]` array:

| Seq | Phase_No | Sub_Step | Action_Code | Phase_ID | Ingredient | Target (kg) |
|-----|----------|----------|-------------|----------|------------|-------------|
| 1 | 10 | 10 | x10010 | p0010 | LS in Line | 371.71 |
| 2 | 10 | 20 | x10020 | p0010 | RO-Water | 372.87 |
| 3 | 10 | 30 | x10030 | p0010 | White Sugar W150 | 250.0 |
| 4 | 20 | 10 | x20010 | p0020 | *(empty)* | 0.0 |
| 5 | 30 | 10 | x30010 | p0030 | Potassium Sorbate | 0.8 |
| 6 | 30 | 20 | x30020 | p0030 | Sodium Benzoate | 0.2 |
| 7 | 30 | 30 | x30030 | p0030 | Malic Acid | 0.115 |
| 8 | 30 | 40 | x30040 | p0030 | Caramel Colour III | 0.2 |
| 9 | 30 | 50 | x30050 | p0030 | RO-Water | 4.0 |
| 10 | 40 | 10 | x40010 | p0040 | *(empty)* | 0.0 |
| 11 | 45 | 10 | x45010 | p0045 | Sugar Flavour SG-01 | 0.11 |
| 12 | 50 | 10 | x50010 | p0050 | *(empty)* | 0.0 |
| 13 | 60 | 10 | x60010 | p0060 | *(empty)* | 0.0 |
| 14-128 | 0 | 0 | | | *(unused — Seq=0)* | 0.0 |

> The PLC reads `Total_Steps = 13`, so it knows to stop after Seq 13 and ignore Steps[14] to Steps[128].

---

## 🐍 Python Serialization Tip
When you write the `.serialize()` function in `plc_interface.py`:

```python
import struct

def pack_s7_string(s: str, max_len: int) -> bytes:
    s_bytes = s.encode('ascii')[:max_len]
    return struct.pack('BB', max_len, len(s_bytes)) + s_bytes.ljust(max_len, b'\x00')

# Pack Header (52 bytes)
header = b""
header += pack_s7_string(batch_id, 20)       # +0
header += pack_s7_string(sku_id, 20)          # +22
header += struct.pack('>h', hmi_command)      # +44
header += struct.pack('>h', total_steps)      # +46
header += struct.pack('>h', active_step)      # +48
header += struct.pack('?', cmd_load_recipe)   # +50
header += b'\x00'                             # +51 padding

# Pack Each Step (78 bytes each)
for step in steps:
    header += struct.pack('>hhh', step.seq, step.phase_no, step.sub_step)  # +0,2,4
    header += pack_s7_string(step.action_code, 10)   # +6
    header += pack_s7_string(step.phase_id, 10)      # +18
    header += pack_s7_string(step.re_code, 20)        # +30
    header += struct.pack('>ffffff', 
        step.target_weight, step.temp_sp, step.temp_low,
        step.temp_high, step.agitator_sp, step.highshear_sp)  # +52..+76
    header += struct.pack('>h', step.step_time)       # +76

# Total payload = 52 + (128 * 78) = 10,036 bytes
plc.db_write(db_number=1511, start=0, data=header)
```
