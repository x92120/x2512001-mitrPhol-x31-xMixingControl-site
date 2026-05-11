# Recipe Transfer Protocol — App to PLC

> How to reliably transfer ~29 KB of recipe data to the PLC  
> and **prove** every byte arrived correctly.

---

## The Challenge

| Issue | Detail |
|-------|--------|
| **PDU Size Limit** | S7-1200 has a max PDU (Protocol Data Unit) of **240 bytes per request**. You CANNOT write 29 KB in one shot. |
| **Network Reliability** | Ethernet packets can be dropped, delayed, or corrupted |
| **Partial Write** | If the transfer is interrupted halfway, the PLC has a half-loaded recipe = DANGEROUS |
| **Verification** | How does the operator know ALL 13 steps arrived correctly? |

---

## Solution: Chunked Transfer with Checksum Verification

### The 4-Stage Protocol

```
Stage 1          Stage 2          Stage 3          Stage 4
PREPARE          TRANSFER         VERIFY           ACTIVATE
─────────        ─────────        ─────────        ─────────
Lock recipe      Write chunks     Read back &      Set RecipeReady
Set flag         phase by phase   compare CRC      = TRUE
RecipeReady      via Node-RED     App vs PLC       PLC can start
= FALSE          S7 writes       checksum match?
```

---

## Stage 1: PREPARE — Lock the Recipe Slot

Before writing any data, tell the PLC "I'm about to download a new recipe."

```
App → Node-RED → PLC:
  DB1780.RecipeReady   = FALSE     ← PLC must NOT start with old data
  DB1780.RecipeLoading = TRUE      ← New flag: download in progress
  DB1780.BatchID       = ""        ← Clear old batch
  DB1780.CRC_App       = 0         ← Clear old checksum
```

**PLC Logic:** If `RecipeLoading = TRUE`, ignore any `StartCmd`. This prevents accidental start during transfer.

---

## Stage 2: TRANSFER — Write Data in Chunks

### How S7 Protocol Works

```
One S7 Write Request = max ~200 bytes of data (within 240-byte PDU)

DB1780 total = ~29,000 bytes
29,000 ÷ 200 = 145 write requests needed (takes ~2-3 seconds)
```

### Node-RED Handles the Chunking

The App does NOT write directly to the PLC. Instead:

```
┌──────────┐  HTTP POST   ┌──────────┐  S7 Write ×145  ┌──────────┐
│  FastAPI  │────────────►│ Node-RED  │────────────────►│   PLC    │
│  Backend  │  Full JSON  │  Bridge   │  200 bytes each │ DB1780   │
└──────────┘  (one shot)  └──────────┘  (sequential)   └──────────┘
```

**Node-RED Flow:**

```javascript
// Node-RED Function: Break recipe JSON into S7 write commands
const recipe = msg.payload;

// 1. Write Header fields one by one
const writes = [];
writes.push({ addr: "DB1780,S0.30",  value: recipe.Header.PlanID });
writes.push({ addr: "DB1780,S32.20", value: recipe.Header.BatchID });
writes.push({ addr: "DB1780,S54.20", value: recipe.Header.SkuID });
// ... etc

// 2. Write each Process/Step
for (let p = 0; p < recipe.Processes.length; p++) {
    const proc = recipe.Processes[p];
    const baseOffset = HEADER_SIZE + (p * PROCESS_SIZE);
    
    // Write process header
    writes.push({ addr: `DB1780,INT${baseOffset}`, value: proc.ProcessNo });
    writes.push({ addr: `DB1780,INT${baseOffset+2}`, value: proc.PhaseID });
    
    // Write each step (8 per process)
    for (let s = 0; s < 8; s++) {
        const step = proc.Steps[s];
        const stepOffset = baseOffset + PROC_HEADER + (s * STEP_SIZE);
        
        writes.push({ addr: `DB1780,INT${stepOffset}`,   value: step.StepNo });
        writes.push({ addr: `DB1780,INT${stepOffset+2}`,  value: step.ActionCode });
        writes.push({ addr: `DB1780,REAL${stepOffset+4}`, value: step.Require });
        // ... etc for all fields
    }
}

// 3. Execute writes sequentially
msg.writes = writes;
return msg;
```

### Transfer Time Estimate

| PLC Model | S7 Write Speed | Time for 145 writes |
|-----------|----------------|---------------------|
| S7-1200 | ~10-15ms per write | **~1.5-2.2 seconds** |
| S7-1500 | ~5-8ms per write | **~0.7-1.2 seconds** |

This is fast enough — operator won't even notice.

---

## Stage 3: VERIFY — Prove No Data Lost

### Method A: CRC Checksum (Recommended)

```
┌──────────┐                    ┌──────────┐
│   App    │  Calculate CRC     │   PLC    │  Calculate CRC
│          │  on full recipe    │          │  on received data
│          │  CRC_App = 0xA3F7  │          │  CRC_PLC = 0xA3F7
│          │                    │          │
│          │  Write CRC_App     │          │  Compare:
│          │  to DB1780  ──────►│          │  CRC_App == CRC_PLC?
│          │                    │          │  ✅ Match → Data OK
└──────────┘                    └──────────┘
```

**App Side (Python/FastAPI):**

```python
import struct
import zlib

def calculate_recipe_crc(recipe_data: dict) -> int:
    """Calculate CRC32 of all recipe values in order."""
    buffer = bytearray()
    
    # Pack header
    buffer += recipe_data["Header"]["BatchID"].encode().ljust(20, b'\x00')
    buffer += recipe_data["Header"]["SkuID"].encode().ljust(20, b'\x00')
    buffer += struct.pack('>H', recipe_data["Header"]["ProcessCount"])
    
    # Pack each step in order
    for proc in recipe_data["Processes"]:
        buffer += struct.pack('>H', proc["ProcessNo"])
        buffer += struct.pack('>H', proc["StepCount"])
        for step in proc["Steps"]:
            buffer += struct.pack('>H', step["StepNo"])
            buffer += struct.pack('>H', step["ActionCode"])
            buffer += struct.pack('>f', step["Require"])
            buffer += struct.pack('>f', step["Temperature"])
            buffer += struct.pack('>f', step["AgitatorRPM"])
            buffer += struct.pack('>f', step["HighShearRPM"])
            buffer += struct.pack('>H', step["StepTime"])
    
    crc = zlib.crc32(buffer) & 0xFFFFFFFF
    return crc
```

**PLC Side (SCL):**

```pascal
// Simple checksum: sum all critical numeric values
// (Full CRC32 is complex in SCL, use additive checksum instead)

FUNCTION "FC_CalcChecksum" : DInt
VAR_TEMP
    i, j       : Int;
    checksum   : DInt;
    stepData   : "UDT_ProcessStep";
END_VAR

BEGIN
    #checksum := 0;
    
    FOR #i := 0 TO "DB_RecipeData".ProcessCount - 1 DO
        #checksum := #checksum + "DB_RecipeData".Processes[#i].ProcessNo;
        #checksum := #checksum + "DB_RecipeData".Processes[#i].StepCount;
        
        FOR #j := 0 TO "DB_RecipeData".Processes[#i].StepCount - 1 DO
            #stepData := "DB_RecipeData".Processes[#i].Steps[#j];
            #checksum := #checksum + #stepData.StepNo;
            #checksum := #checksum + #stepData.ActionCode;
            #checksum := #checksum + REAL_TO_DINT(#stepData.Require * 100.0);
            #checksum := #checksum + REAL_TO_DINT(#stepData.Temperature * 100.0);
            #checksum := #checksum + REAL_TO_DINT(#stepData.AgitatorRPM);
            #checksum := #checksum + REAL_TO_DINT(#stepData.HighShearRPM);
            #checksum := #checksum + #stepData.StepTime;
        END_FOR;
    END_FOR;
    
    "FC_CalcChecksum" := #checksum;
END_FUNCTION
```

### Method B: Readback Verification (Simpler but Slower)

After writing all data, Node-RED reads back every field and the App compares:

```
App sends recipe → Node-RED writes to PLC → Node-RED reads back from PLC → App compares

For each field:
  IF sent_value != readback_value THEN
    → ERROR: Data mismatch at Process[2].Steps[3].Temperature
    → RETRY transfer
```

**Pros:** Simple, no PLC code needed  
**Cons:** Takes 2× time (write + read), ~4 seconds total

### Method C: Step Count + Key Field Spot-Check (Fastest)

Quick verification — don't check everything, just critical fields:

```
App writes:
  ProcessCount = 7
  TotalSteps = 13
  Processes[0].Steps[0].ActionCode = 10030
  Processes[6].Steps[0].StepTime = 300    (last step)
  CRC_Simple = sum of all StepNo + ActionCode values

Node-RED reads back these 5 values and compares.
If all match → 99.99% confidence data is correct.
```

---

## Stage 4: ACTIVATE — Mark Recipe Ready

Only after verification passes:

```
App → Node-RED → PLC:
  DB1780.CRC_App       = calculated_checksum
  DB1780.RecipeLoading = FALSE
  DB1780.RecipeReady   = TRUE     ← NOW the PLC is allowed to start
```

**PLC Logic in FB1780:**

```pascal
// Only allow start if recipe is verified
IF "DB_RecipeData".StartCmd AND "DB_RecipeData".RecipeReady 
   AND NOT "DB_RecipeData".RecipeLoading THEN
    
    // Optional: PLC calculates its own checksum and compares
    IF "FC_CalcChecksum"() = "DB_RecipeData".CRC_App THEN
        "DB_RecipeData".PLC_State := 1;  // Start!
    ELSE
        "DB_RecipeData".Error_Code := 4;  // CRC mismatch!
        // DO NOT START — recipe may be corrupted
    END_IF;
END_IF;
```

---

## What the Operator Sees on the Frontend

```
┌────────────────────────────────────────────────────┐
│  📥 Downloading Recipe to PLC...                   │
│                                                    │
│  ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓░░░░░  78%                │
│                                                    │
│  Phase 1/7: p0010 — Batching .............. ✅     │
│  Phase 2/7: p0020 — Heating ............... ✅     │
│  Phase 3/7: p0030 — Dissolving ............ ✅     │
│  Phase 4/7: p0040 — Pre-Heat .............. ⏳     │
│  Phase 5/7: p0045 — Flavoring ............. ⏳     │
│  Phase 6/7: p0050 — Pasteurize ............ ⏳     │
│  Phase 7/7: p0060 — Cooling ............... ⏳     │
│                                                    │
│  Verifying checksum...                             │
└────────────────────────────────────────────────────┘

         ↓ (after 2-3 seconds)

┌────────────────────────────────────────────────────┐
│  ✅ Recipe Downloaded Successfully!                │
│                                                    │
│  Batch:  P260309-01-01-001                         │
│  SKU:    S77S743200 — Cafe Amazon                  │
│  Steps:  13 steps in 7 phases                      │
│  CRC:    0xA3F7B2C1 ✅ Match                      │
│                                                    │
│  ┌────────────────────────────────────────────┐    │
│  │  🟢 START PRODUCTION                       │    │
│  └────────────────────────────────────────────┘    │
└────────────────────────────────────────────────────┘
```

---

## Recommended Approach

| Method | Reliability | Speed | PLC Code Needed? |
|--------|------------|-------|-------------------|
| **A: CRC Checksum** | ⭐⭐⭐⭐⭐ | Fast (2s) | Yes (FC_CalcChecksum) |
| **B: Full Readback** | ⭐⭐⭐⭐⭐ | Slow (4s) | No |
| **C: Spot-Check** | ⭐⭐⭐⭐ | Fastest (1s) | No |

**My Recommendation:** Use **Method A (CRC) + Method C (Spot-Check)** together:
1. Calculate additive checksum on App side
2. Write recipe + checksum to PLC
3. Quick spot-check: read back ProcessCount + first step + last step
4. PLC calculates its own checksum on StartCmd
5. If both match → production is safe to start

---

## New DB1780 Fields Required

Add these to the header section:

```pascal
// ── Transfer Control ──
RecipeLoading   : Bool;      // TRUE during transfer (blocks StartCmd)
CRC_App         : DInt;      // Checksum calculated by App
CRC_PLC         : DInt;      // Checksum calculated by PLC
CRC_Match       : Bool;      // TRUE if CRC_App == CRC_PLC
Transfer_Error  : Int;       // 0=OK, 1=Timeout, 2=CRC Mismatch
```

---

## Failure Recovery

| Scenario | What Happens |
|----------|-------------|
| **Network drops during transfer** | `RecipeLoading = TRUE`, `RecipeReady = FALSE` → PLC cannot start. App retries from scratch. |
| **CRC mismatch** | App shows error "Recipe verification failed!" + retries automatically (up to 3 times) |
| **PLC power loss during transfer** | DB1780 is in retentive memory. On power-up, `RecipeLoading = TRUE` → PLC stays idle. App must re-download. |
| **App crashes during transfer** | Same as network drop — PLC stays in "loading" state. App restart detects `RecipeLoading = TRUE` and re-downloads. |
