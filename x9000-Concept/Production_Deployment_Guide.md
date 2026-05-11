# Production Deployment Guide — PLC Mixing Control V2

> This document explains **exactly** what needs to happen on each layer of the system to move from our tested mock environment to a real, running production line.

---

## Architecture Overview

```
┌──────────────────┐      ┌─────────────┐      ┌──────────────┐      ┌────────────┐
│   Nuxt Frontend  │◄─ws──┤  FastAPI     │◄─amqp┤  Node-RED    │◄─s7──┤ Siemens PLC│
│  x62-MixingV2    │      │  Backend     │      │  Middleware   │      │ S7-1200/   │
│  (Stateless UI)  │──────►│  (Supervisor)│──────►│  (Bridge)    │──────►│ S7-1500    │
└──────────────────┘      └─────────────┘      └──────────────┘      └────────────┘
       Browser              Port 8023           Port 1880              192.168.x.x
```

**Data Flow:**
1. **Download:** Nuxt → FastAPI → Node-RED → PLC (write recipe once)
2. **Telemetry:** PLC → Node-RED (poll 500ms) → RabbitMQ → FastAPI → Nuxt (live state)
3. **Heartbeat:** FastAPI → RabbitMQ → Node-RED → PLC (toggle bit every 1s)

---

## PART A: PLC Code (TIA Portal)

> **Important:** All code below is in SCL (Structured Control Language) for Siemens TIA Portal V16+.
> Your PLC engineer should create these in the TIA Portal project.

### A1. User-Defined Types (UDTs)

Create these two UDTs first. They define the shape of every recipe step and the overall recipe.

```pascal
// ═══════════════════════════════════════════════
// UDT: "UDT_ProcessStep"
// Size: ~136 bytes per step
// ═══════════════════════════════════════════════
TYPE "UDT_ProcessStep"
VERSION : 0.1
   STRUCT
      StepNo        : Int;            // Sub-step number (1, 2, 3...)
      ActionCode    : Int;            // Action code (10010=Setup, 21010=Manual Add, etc.)
      ReCode        : String[25];     // Recipe ingredient code
      SapCode       : String[20];     // SAP Material code
      Destination   : Int;            // Target vessel (0=MixTank, 1=Hopper...)
      Require       : Real;           // Required weight (kg)
      LowTol        : Real;           // Low tolerance (kg)
      HighTol       : Real;           // High tolerance (kg)
      Temperature   : Real;           // Setpoint temperature (°C)
      TempLow       : Real;           // Temp low limit
      TempHigh      : Real;           // Temp high limit
      AgitatorRPM   : Real;           // Agitator speed setpoint (RPM)
      HighShearRPM  : Real;           // High-shear mixer speed (RPM)
      StepTime      : Int;            // Step duration (seconds)
      StepTimerCtl  : Int;            // Timer control mode (0=none, 1=auto, 2=manual)
      SetupStep     : Int;            // Setup step flag
      Condition     : Int;            // Step condition code
      QcTemp        : Bool;           // Requires QC temperature check
      RecordSteam   : Bool;           // Record steam pressure
      RecordCTW     : Bool;           // Record CTW data
      BrixRecord    : Bool;           // Requires Brix recording
      PhRecord      : Bool;           // Requires pH recording
      MasterStep    : Bool;           // Is a master step (phase start)
      StepActive    : Bool;           // Step has valid data (not empty)
      BrixSP        : Real;           // Brix setpoint
      PhSP          : Real;           // pH setpoint
   END_STRUCT;
END_TYPE
```

```pascal
// ═══════════════════════════════════════════════
// UDT: "UDT_Process" (Phase)
// Each process contains up to 8 steps
// ═══════════════════════════════════════════════
TYPE "UDT_Process"
VERSION : 0.1
   STRUCT
      ProcessNo     : Int;            // Phase number (10, 20, 30...)
      PhaseID       : Int;            // Phase ID from DB
      StepCount     : Int;            // Number of active steps in this phase
      ProcessActive : Bool;           // Phase has valid data
      Steps         : Array[0..7] of "UDT_ProcessStep";
   END_STRUCT;
END_TYPE
```

### A2. Data Block — DB1780 "DB_RecipeData"

This is the main recipe data block that the PC writes to and the PLC reads from.

```pascal
// ═══════════════════════════════════════════════
// DB1780: "DB_RecipeData"
// The PC writes recipe data here BEFORE starting
// ═══════════════════════════════════════════════
DATA_BLOCK "DB_RecipeData"
{ S7_Optimized_Access := 'FALSE' }
VERSION : 0.1
   STRUCT
      // ── Header (written by PC) ──
      PlanID        : String[30];
      BatchID       : String[20];
      SkuID         : String[20];
      SkuName       : String[50];
      PlantID       : Int;
      BatchSize     : Real;
      ProcessCount  : Int;           // Number of active phases
      
      // ── Control Flags (written by PC) ──
      RecipeReady   : Bool;          // PC sets TRUE after download complete
      StartCmd      : Bool;          // PC sets TRUE to start batch
      PauseCmd      : Bool;          // PC sets TRUE to pause
      AbortCmd      : Bool;          // PC sets TRUE to emergency stop
      PC_Heartbeat  : Bool;          // PC toggles every 1 second
      
      // ── Status (written by PLC) ──
      PLC_State         : Int;       // 0=Idle, 1=Running, 2=WaitManual, 3=Paused, 4=Done, 9=Error
      Current_Process   : Int;       // Current active phase index (0-31)
      Current_Step      : Int;       // Current active step index within phase (0-7)
      Current_Step_Flat : Int;       // Flat step counter across all phases (1-based)
      Step_Timer_Act    : Int;       // Remaining seconds on current step timer
      Step_Complete     : Bool;      // Pulse: PLC sets TRUE when a step finishes
      Batch_Complete    : Bool;      // TRUE when all steps are done
      Error_Code        : Int;       // 0=None, 1=Heartbeat Lost, 2=Timeout
      
      // ── Actuals (written by PLC from I/O) ──
      MixTank_Temp_Act  : Real;      // Actual tank temperature
      MixTank_Weight_Act: Real;      // Actual tank weight
      Agitator_Act      : Real;      // Actual agitator RPM
      HighShear_Act     : Real;      // Actual high-shear RPM
      Hopper_Weight_Act : Real;      // Actual hopper weight
      Brix_Act          : Real;      // Actual Brix reading
      PH_Act            : Real;      // Actual pH reading
      
      // ── Recipe Array (32 phases × 8 steps) ──
      Processes     : Array[0..31] of "UDT_Process";
   END_STRUCT;
BEGIN
END_DATA_BLOCK
```

> **⚠️ CRITICAL:** Set `S7_Optimized_Access := 'FALSE'` so Node-RED can read/write using absolute byte offsets (e.g., `DB1780,DBD100`).

### A3. Function Block — FB1780 "FB_MixingSequencer"

This is the **brain** of the system. It runs in a cyclic OB (e.g., OB1 or OB35) and manages the step-by-step execution.

```pascal
// ═══════════════════════════════════════════════════════════
// FB1780: "FB_MixingSequencer"
// Main sequencer logic — runs in OB1 every scan cycle
// ═══════════════════════════════════════════════════════════
FUNCTION_BLOCK "FB_MixingSequencer"
VERSION : 0.1

VAR_INPUT
    // Analog inputs from field instruments
    Act_MixTank_Temp   : Real;
    Act_MixTank_Weight : Real;
    Act_Agitator_RPM   : Real;
    Act_HighShear_RPM  : Real;
    Act_Hopper_Weight  : Real;
    Act_Brix           : Real;
    Act_PH             : Real;
END_VAR

VAR_OUTPUT
    // Analog outputs to field devices
    SP_Agitator_RPM    : Real;
    SP_HighShear_RPM   : Real;
    SP_Temperature     : Real;
END_VAR

VAR
    stepTimer          : TON;         // IEC Timer for step duration
    heartbeatTimer     : TON;         // Heartbeat watchdog timer
    lastHeartbeat      : Bool;        // Previous heartbeat state
    flatStepCounter    : Int;         // Running count across all phases
END_VAR

VAR_TEMP
    curProcess         : Int;
    curStep            : Int;
    stepData           : "UDT_ProcessStep";
    stepTimeSec        : Time;
END_VAR

BEGIN

// ═══ 1. UPDATE ACTUALS ═══
"DB_RecipeData".MixTank_Temp_Act   := Act_MixTank_Temp;
"DB_RecipeData".MixTank_Weight_Act := Act_MixTank_Weight;
"DB_RecipeData".Agitator_Act       := Act_Agitator_RPM;
"DB_RecipeData".HighShear_Act      := Act_HighShear_RPM;
"DB_RecipeData".Hopper_Weight_Act  := Act_Hopper_Weight;
"DB_RecipeData".Brix_Act           := Act_Brix;
"DB_RecipeData".PH_Act             := Act_PH;

// ═══ 2. HEARTBEAT WATCHDOG ═══
// If PC_Heartbeat stops toggling for 5 seconds → PC is dead
IF "DB_RecipeData".PC_Heartbeat <> #lastHeartbeat THEN
    #lastHeartbeat := "DB_RecipeData".PC_Heartbeat;
    #heartbeatTimer(IN := FALSE, PT := T#5s);  // Reset timer
END_IF;
#heartbeatTimer(IN := TRUE, PT := T#5s);

IF #heartbeatTimer.Q AND "DB_RecipeData".PLC_State = 1 THEN
    // PC lost! But don't stop the batch — just log the error
    "DB_RecipeData".Error_Code := 1;  // Heartbeat lost
    // If current step is manual (ActionCode 21010), pause
    #curProcess := "DB_RecipeData".Current_Process;
    #curStep    := "DB_RecipeData".Current_Step;
    #stepData   := "DB_RecipeData".Processes[#curProcess].Steps[#curStep];
    IF #stepData.ActionCode = 21010 THEN
        "DB_RecipeData".PLC_State := 2;  // WaitManual — safe pause
    END_IF;
    // Automatic steps (mixing, heating) CONTINUE running
END_IF;

// ═══ 3. COMMAND HANDLING ═══
// Start
IF "DB_RecipeData".StartCmd AND "DB_RecipeData".RecipeReady THEN
    IF "DB_RecipeData".PLC_State = 0 OR "DB_RecipeData".PLC_State = 3 THEN
        "DB_RecipeData".PLC_State := 1;  // Running
        "DB_RecipeData".StartCmd  := FALSE;
        "DB_RecipeData".Error_Code := 0;
        IF "DB_RecipeData".Current_Process = 0 AND "DB_RecipeData".Current_Step = 0 THEN
            #flatStepCounter := 1;
        END_IF;
    END_IF;
END_IF;

// Pause
IF "DB_RecipeData".PauseCmd THEN
    "DB_RecipeData".PLC_State := 3;  // Paused
    "DB_RecipeData".PauseCmd  := FALSE;
END_IF;

// Abort
IF "DB_RecipeData".AbortCmd THEN
    "DB_RecipeData".PLC_State     := 0;  // Idle
    "DB_RecipeData".AbortCmd      := FALSE;
    "DB_RecipeData".Current_Process := 0;
    "DB_RecipeData".Current_Step    := 0;
    #flatStepCounter := 0;
    SP_Agitator_RPM  := 0.0;
    SP_HighShear_RPM := 0.0;
    SP_Temperature   := 0.0;
END_IF;

// ═══ 4. MAIN SEQUENCER (only when Running) ═══
IF "DB_RecipeData".PLC_State = 1 THEN

    #curProcess := "DB_RecipeData".Current_Process;
    #curStep    := "DB_RecipeData".Current_Step;
    
    // Safety: check bounds
    IF #curProcess > 31 OR NOT "DB_RecipeData".Processes[#curProcess].ProcessActive THEN
        "DB_RecipeData".PLC_State     := 4;  // Done
        "DB_RecipeData".Batch_Complete := TRUE;
        SP_Agitator_RPM  := 0.0;
        SP_HighShear_RPM := 0.0;
        RETURN;
    END_IF;
    
    // Get current step data
    #stepData := "DB_RecipeData".Processes[#curProcess].Steps[#curStep];
    
    // ── Apply setpoints to outputs ──
    SP_Agitator_RPM  := #stepData.AgitatorRPM;
    SP_HighShear_RPM := #stepData.HighShearRPM;
    SP_Temperature   := #stepData.Temperature;
    
    // ── Update flat counter for UI ──
    "DB_RecipeData".Current_Step_Flat := #flatStepCounter;
    
    // ── MANUAL STEP (ActionCode 21010): Wait for operator ──
    IF #stepData.ActionCode = 21010 THEN
        "DB_RecipeData".PLC_State := 2;  // WaitManual
        // The PC will set StartCmd=TRUE again when operator scans/confirms
        RETURN;
    END_IF;
    
    // ── TIMED STEP: Run step timer ──
    IF #stepData.StepTime > 0 THEN
        #stepTimeSec := INT_TO_TIME(#stepData.StepTime * 1000);
        #stepTimer(IN := TRUE, PT := #stepTimeSec);
        "DB_RecipeData".Step_Timer_Act := 
            TIME_TO_INT(#stepTimeSec - #stepTimer.ET) / 1000;
        
        IF NOT #stepTimer.Q THEN
            RETURN;  // Still counting, come back next scan
        END_IF;
        // Timer finished — reset and advance
        #stepTimer(IN := FALSE, PT := #stepTimeSec);
    END_IF;
    
    // ── STEP COMPLETE → advance ──
    "DB_RecipeData".Step_Complete := TRUE;  // Pulse for Node-RED to catch
    
    // Move to next step in this phase
    IF #curStep + 1 < "DB_RecipeData".Processes[#curProcess].StepCount THEN
        "DB_RecipeData".Current_Step := #curStep + 1;
        #flatStepCounter := #flatStepCounter + 1;
    ELSE
        // Move to next phase
        "DB_RecipeData".Current_Step := 0;
        "DB_RecipeData".Current_Process := #curProcess + 1;
        #flatStepCounter := #flatStepCounter + 1;
        
        // Check if we've exceeded all active phases
        IF #curProcess + 1 >= "DB_RecipeData".ProcessCount THEN
            "DB_RecipeData".PLC_State     := 4;  // Done
            "DB_RecipeData".Batch_Complete := TRUE;
            SP_Agitator_RPM  := 0.0;
            SP_HighShear_RPM := 0.0;
        END_IF;
    END_IF;
    
END_IF;

END_FUNCTION_BLOCK
```

### A4. Calling FB1780 in OB1

In your main program (OB1), create an instance DB and call the function block:

```pascal
// In OB1 (Main Program)
"FB_MixingSequencer_DB"(
    Act_MixTank_Temp   := "AI_MixTank_TT01",      // Your analog input tag
    Act_MixTank_Weight := "AI_MixTank_WT01",
    Act_Agitator_RPM   := "AI_Agitator_Speed",
    Act_HighShear_RPM  := "AI_HighShear_Speed",
    Act_Hopper_Weight  := "AI_Hopper_WT01",
    Act_Brix           := "AI_Brix_Sensor",
    Act_PH             := "AI_PH_Sensor",
    SP_Agitator_RPM    => "AO_Agitator_SP",        // Your analog output tag
    SP_HighShear_RPM   => "AO_HighShear_SP",
    SP_Temperature     => "AO_Temperature_SP"
);
```

> **Note:** Replace `"AI_xxx"` and `"AO_xxx"` with your actual I/O tag names from the TIA Portal hardware configuration.

---

## PART B: Node-RED Configuration

### B1. Install Required Nodes

```bash
cd ~/.node-red
npm install node-red-contrib-s7
npm install node-red-contrib-amqp
```

### B2. S7 Connection Configuration

In Node-RED, create an S7 connection:
| Setting        | Value                    |
|----------------|--------------------------|
| Host           | `192.168.1.1` (your PLC) |
| Port           | `102`                    |
| Rack           | `0`                      |
| Slot           | `1`                      |
| Cycle Time     | `500` ms                 |

### B3. S7 Variable Mapping (Read from PLC → Publish to RabbitMQ)

Create an **S7-In** node that reads these DB1780 addresses every 500ms:

| Variable Name      | S7 Address           | Type    |
|---------------------|----------------------|---------|
| PLC_State           | `DB1780,INT18`       | INT     |
| Current_Process     | `DB1780,INT20`       | INT     |
| Current_Step        | `DB1780,INT22`       | INT     |
| Current_Step_Flat   | `DB1780,INT24`       | INT     |
| Step_Timer_Act      | `DB1780,INT26`       | INT     |
| Step_Complete       | `DB1780,X28.0`       | BOOL    |
| Batch_Complete      | `DB1780,X28.1`       | BOOL    |
| Error_Code          | `DB1780,INT30`       | INT     |
| MixTank_Temp_Act    | `DB1780,REAL32`      | REAL    |
| MixTank_Weight_Act  | `DB1780,REAL36`      | REAL    |
| Agitator_Act        | `DB1780,REAL40`      | REAL    |
| HighShear_Act       | `DB1780,REAL44`      | REAL    |
| Hopper_Weight_Act   | `DB1780,REAL48`      | REAL    |
| Brix_Act            | `DB1780,REAL52`      | REAL    |
| PH_Act              | `DB1780,REAL56`      | REAL    |
| BatchID             | `DB1780,S34.20`      | STRING  |

> **⚠️ Important:** The exact byte offsets above are **approximate**. After you create DB1780 in TIA Portal with `Optimized Access = FALSE`, open the DB and look at the **Offset** column. Use those exact values in Node-RED.

### B4. Node-RED Flow Logic

```
[S7-In: Read PLC every 500ms]
       │
       ▼
[Function: Compare with previous state]
       │ (only publish if PLC_State or Current_Step changed)
       ▼
[AMQP-Out: Publish to RabbitMQ exchange "plc.mixing.state"]
       │
       ▼
  FastAPI Consumer picks it up
```

**Function Node (change detection):**
```javascript
// Store previous state in flow context
var prev = flow.get('plc_state') || {};
var cur  = msg.payload;

// Only publish if something changed
if (prev.PLC_State !== cur.PLC_State || 
    prev.Current_Step_Flat !== cur.Current_Step_Flat ||
    prev.Step_Complete !== cur.Step_Complete) {
    
    flow.set('plc_state', cur);
    msg.payload = {
        PLC_State: cur.PLC_State,
        Current_Process: cur.Current_Process,
        Current_Step: cur.Current_Step,
        Current_Step_Flat: cur.Current_Step_Flat,
        Step_Timer_Act: cur.Step_Timer_Act,
        Step_Complete: cur.Step_Complete,
        Batch_Complete: cur.Batch_Complete,
        BatchID: cur.BatchID,
        MixTank_Temp_Act: cur.MixTank_Temp_Act,
        MixTank_Weight_Act: cur.MixTank_Weight_Act,
        Agitator_Act: cur.Agitator_Act,
        HighShear_Act: cur.HighShear_Act,
        timestamp: new Date().toISOString()
    };
    return msg;
}
return null; // Don't publish if nothing changed
```

### B5. Writing Recipe TO PLC (PC → Node-RED → PLC)

Create an **HTTP-In** node (POST `/api/plc/write-recipe`) that accepts the JSON recipe from FastAPI and writes it to DB1780 using S7-Out nodes.

**Flow:**
```
[HTTP-In: POST /api/plc/write-recipe]
       │
       ▼
[Function: Map JSON to S7 writes]
       │
       ▼
[S7-Out: Write header fields]
[S7-Out: Write Process[0].Steps[0..7]]
[S7-Out: Write Process[1].Steps[0..7]]
  ... (loop through all active processes)
       │
       ▼
[S7-Out: Write RecipeReady = TRUE]
       │
       ▼
[HTTP-Response: 200 OK]
```

### B6. Heartbeat Relay (PC → PLC)

```
[AMQP-In: Subscribe "pc.heartbeat"]
       │
       ▼
[S7-Out: Write DB1780.PC_Heartbeat (toggle TRUE/FALSE)]
```

---

## PART C: Production Deployment Checklist

### Step 1: PLC Setup (TIA Portal)
- [ ] Create `UDT_ProcessStep` and `UDT_Process` in TIA Portal
- [ ] Create `DB1780` with `Optimized Access = FALSE`
- [ ] Create `FB1780` with the sequencer logic
- [ ] Call `FB1780` in OB1 with correct I/O mappings
- [ ] Download to PLC and verify DB1780 appears in the watch table
- [ ] Note the **exact byte offsets** from TIA Portal's DB view

### Step 2: Node-RED Setup
- [ ] Install `node-red-contrib-s7` and `node-red-contrib-amqp`
- [ ] Configure S7 connection to PLC IP (test with a simple read first)
- [ ] Map the S7 variables using exact offsets from Step 1
- [ ] Create the polling flow (read every 500ms)
- [ ] Create the change-detection function node
- [ ] Create the RabbitMQ publish node
- [ ] Create the recipe-write HTTP endpoint
- [ ] Create the heartbeat relay flow
- [ ] **Test:** Read PLC_State from Node-RED debug panel

### Step 3: FastAPI Backend
- [ ] Update `POST /plc/send-recipe/{batch_id}` to POST the JSON to Node-RED's HTTP endpoint instead of returning it
- [ ] Add RabbitMQ consumer to listen for `plc.mixing.state` events
- [ ] On each event, write to `mixing_batch_step_log` table
- [ ] Add WebSocket broadcast to push state to frontend
- [ ] Add heartbeat publisher (toggle `pc.heartbeat` every 1s)

### Step 4: Frontend (Already Done ✅)
- [x] `x62-MixingControlV2.vue` is stateless
- [x] Reacts to `plantData` telemetry updates
- [x] Recovery on mount works
- [x] `downloadRecipeToPlc()` calls the backend API

### Step 5: Integration Test
- [ ] Load a test batch on the PLC via the UI
- [ ] Verify recipe appears in DB1780 watch table
- [ ] Click START → verify PLC_State changes to 1
- [ ] Watch steps auto-advance in the UI
- [ ] **Pull-the-plug test:** Kill FastAPI at Step 5, restart, verify UI recovers at the correct step
- [ ] **Manual step test:** Verify PLC pauses at ActionCode 21010 and waits for operator confirmation

---

## PART D: Action Code Reference for PLC Logic

The PLC sequencer needs to know which steps are automatic and which require manual intervention:

| Action Code | Description                | PLC Behavior                    |
|-------------|----------------------------|---------------------------------|
| `10010`     | Setup / Initialize         | Auto — apply setpoints, no wait |
| `10020`     | Heating                    | Auto — wait for temp + time     |
| `10030`     | Mixing / Blending          | Auto — run agitator for time    |
| `10040`     | Pasteurize                 | Auto — hold temp for time       |
| `21010`     | Manual Add to Mix Tank     | **MANUAL** — PLC waits for PC   |
| `30020`     | Manual Transfer            | **MANUAL** — PLC waits for PC   |
| `40010`     | QC Check / Record          | **MANUAL** — requires Brix/pH   |

> For all `21010` and `30020` steps, the PLC sets `PLC_State = 2` (WaitManual) and holds position until the PC sends `StartCmd = TRUE` after the operator confirms.

---

## PART E: Network Requirements

| Device      | IP Address       | Port  | Protocol    |
|-------------|------------------|-------|-------------|
| PLC         | `192.168.1.1`    | 102   | S7 (TCP)    |
| Node-RED    | `192.168.1.100`  | 1880  | HTTP        |
| RabbitMQ    | `192.168.1.100`  | 5672  | AMQP        |
| FastAPI     | `192.168.1.100`  | 8023  | HTTP        |
| Nuxt        | `192.168.1.100`  | 3000  | HTTP/WS     |

> All middleware (Node-RED, RabbitMQ, FastAPI, Nuxt) can run on a **single industrial PC**. Only the PLC needs a separate Ethernet connection.

---

## PART F: Safety Considerations

1. **Emergency Stop:** The PLC's hardware E-Stop circuit must be independent of this software. The `AbortCmd` is a software-level stop only.
2. **Heartbeat Timeout:** If `PC_Heartbeat` stops for 5 seconds, the PLC continues automatic steps but pauses manual steps. This prevents product loss.
3. **Recipe Validation:** Before setting `RecipeReady = TRUE`, the PLC should verify `ProcessCount > 0` and `BatchID` is not empty.
4. **Watchdog:** Node-RED should monitor its own S7 connection. If the S7 link drops, it should publish an alarm to RabbitMQ so FastAPI can alert the operator.
