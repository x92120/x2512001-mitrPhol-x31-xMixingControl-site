# PLC Implementation Guide — What to Do in TIA Portal

> **For:** PLC Engineer  
> **PLC Model:** Siemens S7-1200 / S7-1500  
> **Software:** TIA Portal V16+  
> **Language:** SCL (Structured Control Language)

---

## Overview — 5 Things to Create

```
┌──────────────────────────────────────────────────────────┐
│                    TIA Portal Project                     │
│                                                          │
│  1. UDT_ProcessStep     (User-Defined Type)              │
│  2. UDT_Process         (User-Defined Type)              │
│  3. DB1780              (Data Block — Recipe Storage)     │
│  4. FB1780              (Function Block — Sequencer)      │
│  5. OB1 Call            (Main program call)               │
│                                                          │
└──────────────────────────────────────────────────────────┘
```

---

## Step 1: Create UDT_ProcessStep

> **Location:** TIA Portal → PLC_1 → PLC data types → Add new data type

This defines **one recipe step**. Each step has setpoints, material info, and control flags.

```pascal
TYPE "UDT_ProcessStep"
VERSION : 0.1
   STRUCT
      // ── Step Identity ──
      StepNo         : Int;              // Sub-step number (10, 20, 30...)
      ActionCode     : Int;              // 10010=Setup, 10030=Batching, 21010=ManualAdd, 20010=Dissolve
      
      // ── Material ──
      ReCode         : String[25];       // Ingredient code (e.g., "RO-Water", "White Sugar")
      SapCode        : String[20];       // SAP material number
      Destination    : Int;              // 0=MixTank, 1=Hopper, 2=PreMix
      
      // ── Weight ──
      Require        : Real;             // Target weight (kg)
      LowTol         : Real;             // Low tolerance (kg)
      HighTol        : Real;             // High tolerance (kg)
      
      // ── Temperature ──
      Temperature    : Real;             // Setpoint (°C)
      TempLow        : Real;             // Low limit (°C)
      TempHigh       : Real;             // High limit (°C)
      
      // ── Speed ──
      AgitatorRPM    : Real;             // Agitator setpoint (RPM)
      HighShearRPM   : Real;             // High-shear mixer setpoint (RPM)
      
      // ── Timer ──
      StepTime       : Int;              // Step duration (seconds)
      StepTimerCtl   : Int;              // 0=no timer, 1=auto start, 2=manual start
      
      // ── Control ──
      SetupStep      : Int;              // Setup step flag
      Condition      : Int;              // Step condition code
      IsManual       : Bool;             // TRUE = wait for operator (ActionCode 21010/30020)
      
      // ── QC Flags ──
      QcTemp         : Bool;             // Requires QC temperature check
      RecordSteam    : Bool;             // Record steam pressure
      RecordCTW      : Bool;             // Record CTW
      BrixRecord     : Bool;             // Requires Brix recording
      PhRecord       : Bool;             // Requires pH recording
      MasterStep     : Bool;             // Is a phase-start step
      StepActive     : Bool;             // TRUE = this slot has valid data
      
      // ── QC Setpoints ──
      BrixSP         : Real;             // Brix target
      PhSP           : Real;             // pH target
   END_STRUCT;
END_TYPE
```

---

## Step 2: Create UDT_Process

> **Location:** TIA Portal → PLC_1 → PLC data types → Add new data type

This groups **8 steps** into one **phase** (e.g., Phase p0010 = Batching, Phase p0030 = Dissolving).

```pascal
TYPE "UDT_Process"
VERSION : 0.1
   STRUCT
      ProcessNo      : Int;              // Phase number (10, 20, 30, 40...)
      PhaseID        : Int;              // Phase ID from database
      StepCount      : Int;              // Number of active steps (0-8)
      ProcessActive  : Bool;             // TRUE = this phase has data
      Steps          : Array[0..7] of "UDT_ProcessStep";
   END_STRUCT;
END_TYPE
```

---

## Step 3: Create DB1780 — "DB_RecipeData"

> **Location:** TIA Portal → PLC_1 → Program blocks → Add new block → Data Block  
> **⚠️ IMPORTANT:** Right-click DB → Properties → **Uncheck "Optimized block access"**  
> This is required so Node-RED can read/write using absolute byte addresses.

```pascal
DATA_BLOCK "DB_RecipeData"
{ S7_Optimized_Access := 'FALSE' }
VERSION : 0.1
   STRUCT
      // ════════════════════════════════════════════
      //  SECTION A: HEADER (Written by PC at download)
      // ════════════════════════════════════════════
      PlanID            : String[30];     // Production plan ID
      BatchID           : String[20];     // Batch ID (e.g., "P260309-01-01-001")
      SkuID             : String[20];     // SKU code
      SkuName           : String[50];     // SKU name
      PlantID           : Int;            // Plant number (1, 2...)
      BatchSize         : Real;           // Total batch weight (kg)
      ProcessCount      : Int;            // Number of active phases
      TotalSteps        : Int;            // Total steps across all phases
      
      // ════════════════════════════════════════════
      //  SECTION B: COMMANDS (Written by PC)
      // ════════════════════════════════════════════
      RecipeReady       : Bool;           // PC sets TRUE after recipe download complete
      StartCmd          : Bool;           // PC sets TRUE to start/resume batch
      PauseCmd          : Bool;           // PC sets TRUE to pause
      AbortCmd          : Bool;           // PC sets TRUE for emergency stop
      PC_Heartbeat      : Bool;           // PC toggles every 1 second
      
      // ── Step Confirmation (Written by PC) ──
      Confirm_Step      : Bool;           // PC sets TRUE to confirm current step
      Confirm_Phase     : String[10];     // PC echoes back phase being confirmed
      Confirm_SubStep   : Int;            // PC echoes back sub-step being confirmed
      
      // ════════════════════════════════════════════
      //  SECTION C: STATUS (Written by PLC)
      // ════════════════════════════════════════════
      PLC_State         : Int;            // 0=Idle, 1=Executing, 2=WaitConfirm, 3=Paused, 4=Done, 9=Error
      Current_Process   : Int;            // Current phase index (0-31)
      Current_Step      : Int;            // Current step index within phase (0-7)
      Current_Step_Flat : Int;            // Flat step counter (1-based, across all phases)
      Step_Timer_Act    : Int;            // Remaining seconds on step timer
      Step_Done         : Bool;           // TRUE when step execution is finished
      Batch_Complete    : Bool;           // TRUE when all steps done
      Error_Code        : Int;            // 0=None, 1=HeartbeatLost, 2=Timeout, 3=ConfirmMismatch
      
      // ── Current Step Info (for Node-RED readback) ──
      Active_Phase      : String[10];     // Current phase_number (e.g., "p0030")
      Active_SubStep    : Int;            // Current sub_step (e.g., 10)
      Active_ActionCode : Int;            // Current action code (e.g., 21010)
      
      // ════════════════════════════════════════════
      //  SECTION D: ACTUALS (Written by PLC from I/O)
      // ════════════════════════════════════════════
      MixTank_Temp_Act  : Real;           // Actual tank temperature (°C)
      MixTank_Weight_Act: Real;           // Actual tank weight (kg)
      Agitator_RPM_Act  : Real;           // Actual agitator speed (RPM)
      HighShear_RPM_Act : Real;           // Actual high-shear speed (RPM)
      Hopper_Weight_Act : Real;           // Actual hopper weight (kg)
      Brix_Act          : Real;           // Actual Brix reading
      PH_Act            : Real;           // Actual pH reading
      Circulation_Temp  : Real;           // Circulation temperature
      Flow_Rate_Act     : Real;           // Flow rate
      
      // ════════════════════════════════════════════
      //  SECTION E: RECIPE ARRAY (32 phases × 8 steps)
      // ════════════════════════════════════════════
      Processes         : Array[0..31] of "UDT_Process";
   END_STRUCT;
BEGIN
END_DATA_BLOCK
```

### After Creating DB1780

1. **Compile** the data block
2. **Open the DB view** → look at the **Offset** column
3. **Write down the byte offsets** for each field — Node-RED needs these exact numbers
4. Example offset table:

| Field | Expected Offset | Type |
|-------|----------------|------|
| PlanID | DB1780,S0.30 | String[30] |
| BatchID | DB1780,S32.20 | String[20] |
| RecipeReady | DB1780,X??.0 | Bool |
| StartCmd | DB1780,X??.1 | Bool |
| PLC_State | DB1780,INT?? | Int |
| Current_Step_Flat | DB1780,INT?? | Int |
| Step_Done | DB1780,X??.0 | Bool |
| Confirm_Step | DB1780,X??.0 | Bool |
| Processes[0] | DB1780,?? | UDT |

> **Note:** The `??` values depend on how TIA Portal lays out the memory. You MUST check the actual offsets after compiling.

---

## Step 4: Create FB1780 — "FB_MixingSequencer"

> **Location:** TIA Portal → PLC_1 → Program blocks → Add new block → Function Block → SCL

This is the **brain** — it handles the entire step-by-step execution with operator confirmation.

```pascal
FUNCTION_BLOCK "FB_MixingSequencer"
VERSION : 0.1

VAR_INPUT
    // ── Field Instrument Readings ──
    Act_MixTank_Temp    : Real;    // From temperature sensor
    Act_MixTank_Weight  : Real;    // From load cell
    Act_Agitator_RPM    : Real;    // From VFD feedback
    Act_HighShear_RPM   : Real;    // From VFD feedback
    Act_Hopper_Weight   : Real;    // From hopper load cell
    Act_Brix            : Real;    // From Brix sensor (if installed)
    Act_PH              : Real;    // From pH sensor (if installed)
END_VAR

VAR_OUTPUT
    // ── Setpoint Outputs to Field Devices ──
    SP_Agitator_RPM     : Real;    // To agitator VFD
    SP_HighShear_RPM    : Real;    // To high-shear VFD
    SP_Temperature      : Real;    // To heating controller
END_VAR

VAR
    // ── Internal Variables ──
    stepTimer           : TON;     // IEC step timer
    heartbeatTimer      : TON;     // PC watchdog timer
    confirmHoldTimer    : TON;     // Anti-bounce for confirm
    lastHeartbeat       : Bool;    // Previous heartbeat state
    flatStepCounter     : Int;     // Running step count (1-based)
    stepStarted         : Bool;    // Flag: current step outputs have been applied
END_VAR

VAR_TEMP
    iProc               : Int;     // Current process index
    iStep               : Int;     // Current step index
    curStep             : "UDT_ProcessStep";  // Current step data
    stepTimePT          : Time;    // Step time as TIME value
    curPhaseStr         : String[10];  // Current phase as string
END_VAR

BEGIN

// ═══════════════════════════════════════════════════════
//  1. UPDATE ACTUAL VALUES FROM FIELD
// ═══════════════════════════════════════════════════════
"DB_RecipeData".MixTank_Temp_Act   := Act_MixTank_Temp;
"DB_RecipeData".MixTank_Weight_Act := Act_MixTank_Weight;
"DB_RecipeData".Agitator_RPM_Act   := Act_Agitator_RPM;
"DB_RecipeData".HighShear_RPM_Act  := Act_HighShear_RPM;
"DB_RecipeData".Hopper_Weight_Act  := Act_Hopper_Weight;
"DB_RecipeData".Brix_Act           := Act_Brix;
"DB_RecipeData".PH_Act             := Act_PH;


// ═══════════════════════════════════════════════════════
//  2. PC HEARTBEAT WATCHDOG
// ═══════════════════════════════════════════════════════
// If PC_Heartbeat stops toggling for 5 seconds → PC is dead
IF "DB_RecipeData".PC_Heartbeat <> #lastHeartbeat THEN
    #lastHeartbeat := "DB_RecipeData".PC_Heartbeat;
    #heartbeatTimer(IN := FALSE, PT := T#5s);
END_IF;
#heartbeatTimer(IN := TRUE, PT := T#5s);

IF #heartbeatTimer.Q THEN
    // PC lost!
    "DB_RecipeData".Error_Code := 1;
    // If in State 1 (Executing auto step) → continue running (don't ruin product)
    // If in State 2 (Wait Confirm) → stay waiting (safe, outputs held)
    // Only mark error, do NOT stop the process
END_IF;


// ═══════════════════════════════════════════════════════
//  3. COMMAND HANDLING
// ═══════════════════════════════════════════════════════

// ── START Command ──
IF "DB_RecipeData".StartCmd AND "DB_RecipeData".RecipeReady THEN
    IF "DB_RecipeData".PLC_State = 0 THEN
        // Fresh start
        "DB_RecipeData".PLC_State       := 1;
        "DB_RecipeData".Current_Process := 0;
        "DB_RecipeData".Current_Step    := 0;
        "DB_RecipeData".Error_Code      := 0;
        "DB_RecipeData".Batch_Complete  := FALSE;
        #flatStepCounter := 1;
        #stepStarted := FALSE;
    ELSIF "DB_RecipeData".PLC_State = 3 THEN
        // Resume from pause
        "DB_RecipeData".PLC_State := 1;
    END_IF;
    "DB_RecipeData".StartCmd := FALSE;  // Reset command
END_IF;

// ── PAUSE Command ──
IF "DB_RecipeData".PauseCmd THEN
    IF "DB_RecipeData".PLC_State = 1 OR "DB_RecipeData".PLC_State = 2 THEN
        "DB_RecipeData".PLC_State := 3;  // Paused
    END_IF;
    "DB_RecipeData".PauseCmd := FALSE;
END_IF;

// ── ABORT Command ──
IF "DB_RecipeData".AbortCmd THEN
    "DB_RecipeData".PLC_State       := 0;  // Idle
    "DB_RecipeData".Current_Process := 0;
    "DB_RecipeData".Current_Step    := 0;
    "DB_RecipeData".Step_Done       := FALSE;
    "DB_RecipeData".Batch_Complete  := FALSE;
    #flatStepCounter := 0;
    #stepStarted := FALSE;
    SP_Agitator_RPM  := 0.0;
    SP_HighShear_RPM := 0.0;
    SP_Temperature   := 0.0;
    "DB_RecipeData".AbortCmd := FALSE;
END_IF;


// ═══════════════════════════════════════════════════════
//  4. STEP CONFIRMATION HANDLING (State = 2)
// ═══════════════════════════════════════════════════════
IF "DB_RecipeData".PLC_State = 2 AND "DB_RecipeData".Confirm_Step THEN
    
    // Get current step info for validation
    #iProc := "DB_RecipeData".Current_Process;
    #iStep := "DB_RecipeData".Current_Step;
    
    // Safety: Validate that the confirm matches current step
    // (PC must echo back which phase/step it's confirming)
    IF "DB_RecipeData".Confirm_Phase = "DB_RecipeData".Active_Phase
       AND "DB_RecipeData".Confirm_SubStep = "DB_RecipeData".Active_SubStep THEN
        
        // ── CONFIRMED! Reset flags ──
        "DB_RecipeData".Step_Done     := FALSE;
        "DB_RecipeData".Confirm_Step  := FALSE;
        #stepStarted := FALSE;
        
        // ── ADVANCE to next step ──
        IF #iStep + 1 < "DB_RecipeData".Processes[#iProc].StepCount THEN
            // Next step in same phase
            "DB_RecipeData".Current_Step := #iStep + 1;
        ELSE
            // Move to next phase
            "DB_RecipeData".Current_Step := 0;
            "DB_RecipeData".Current_Process := #iProc + 1;
        END_IF;
        
        #flatStepCounter := #flatStepCounter + 1;
        
        // Check if batch is complete
        IF "DB_RecipeData".Current_Process >= "DB_RecipeData".ProcessCount THEN
            "DB_RecipeData".PLC_State      := 4;  // DONE
            "DB_RecipeData".Batch_Complete  := TRUE;
            SP_Agitator_RPM  := 0.0;
            SP_HighShear_RPM := 0.0;
            SP_Temperature   := 0.0;
        ELSE
            "DB_RecipeData".PLC_State := 1;  // Back to EXECUTING
        END_IF;
    ELSE
        // Phase/Step mismatch! Reject the confirmation
        "DB_RecipeData".Error_Code    := 3;  // Confirm mismatch
        "DB_RecipeData".Confirm_Step  := FALSE;  // Reset but don't advance
    END_IF;
END_IF;


// ═══════════════════════════════════════════════════════
//  5. MAIN SEQUENCER — EXECUTE CURRENT STEP (State = 1)
// ═══════════════════════════════════════════════════════
IF "DB_RecipeData".PLC_State = 1 THEN

    #iProc := "DB_RecipeData".Current_Process;
    #iStep := "DB_RecipeData".Current_Step;
    
    // Bounds check
    IF #iProc > 31 OR NOT "DB_RecipeData".Processes[#iProc].ProcessActive THEN
        "DB_RecipeData".PLC_State     := 4;
        "DB_RecipeData".Batch_Complete := TRUE;
        SP_Agitator_RPM  := 0.0;
        SP_HighShear_RPM := 0.0;
        SP_Temperature   := 0.0;
        RETURN;
    END_IF;
    
    // Load current step data
    #curStep := "DB_RecipeData".Processes[#iProc].Steps[#iStep];
    
    // ── Apply setpoints (once per step entry) ──
    IF NOT #stepStarted THEN
        SP_Agitator_RPM  := #curStep.AgitatorRPM;
        SP_HighShear_RPM := #curStep.HighShearRPM;
        SP_Temperature   := #curStep.Temperature;
        #stepStarted     := TRUE;
        
        // Reset timer for new step
        #stepTimer(IN := FALSE, PT := T#1s);
        
        // Update active step info for Node-RED readback
        "DB_RecipeData".Active_SubStep    := #curStep.StepNo;
        "DB_RecipeData".Active_ActionCode := #curStep.ActionCode;
        "DB_RecipeData".Current_Step_Flat := #flatStepCounter;
        
        // Copy phase string
        // Note: In real implementation, build from ProcessNo
        // For now, use phase data from the process
    END_IF;
    
    // ── MANUAL STEP: Go directly to Wait Confirm ──
    IF #curStep.IsManual THEN
        "DB_RecipeData".Step_Done  := TRUE;
        "DB_RecipeData".PLC_State  := 2;  // WAIT_CONFIRM
        // Outputs stay at setpoints (agitator keeps running)
        RETURN;
    END_IF;
    
    // ── TIMED STEP: Run timer ──
    IF #curStep.StepTime > 0 THEN
        #stepTimePT := INT_TO_TIME(#curStep.StepTime * 1000);  // seconds → ms
        #stepTimer(IN := TRUE, PT := #stepTimePT);
        
        // Update remaining time for display
        "DB_RecipeData".Step_Timer_Act :=
            TIME_TO_INT(#stepTimePT - #stepTimer.ET) / 1000;
        
        IF NOT #stepTimer.Q THEN
            RETURN;  // Still counting → come back next scan
        END_IF;
        
        // Timer done → go to WAIT_CONFIRM
        #stepTimer(IN := FALSE, PT := #stepTimePT);
    END_IF;
    
    // ── NO TIMER, NOT MANUAL: immediate → WAIT_CONFIRM ──
    // (e.g., batching steps where weight condition is the trigger)
    "DB_RecipeData".Step_Done  := TRUE;
    "DB_RecipeData".PLC_State  := 2;  // WAIT_CONFIRM
    "DB_RecipeData".Step_Timer_Act := 0;
    
END_IF;

END_FUNCTION_BLOCK
```

---

## Step 5: Call FB1780 in OB1 (Main Program)

> **Location:** TIA Portal → PLC_1 → Program blocks → Main [OB1]

Create an **Instance DB** (TIA Portal creates this automatically when you drag FB1780 into OB1).

```pascal
// ═══ Main Program (OB1) ═══
// Call the Mixing Sequencer every scan cycle

"FB_MixingSequencer_DB"(
    // ── Inputs: Wire to your actual analog input tags ──
    Act_MixTank_Temp    := "AI_TT01_MixTank",       // PT100 / thermocouple
    Act_MixTank_Weight  := "AI_WT01_MixTank",        // Load cell
    Act_Agitator_RPM    := "AI_ST01_Agitator",       // VFD feedback
    Act_HighShear_RPM   := "AI_ST02_HighShear",      // VFD feedback
    Act_Hopper_Weight   := "AI_WT02_Hopper",         // Hopper load cell
    Act_Brix            := "AI_BX01",                // Brix sensor
    Act_PH              := "AI_PH01",                // pH sensor
    
    // ── Outputs: Wire to your actual analog output tags ──
    SP_Agitator_RPM     => "AO_SP01_Agitator",       // To agitator VFD
    SP_HighShear_RPM    => "AO_SP02_HighShear",      // To high-shear VFD
    SP_Temperature      => "AO_SP03_Temperature"     // To heating PID
);
```

> **⚠️ Replace** `"AI_xxx"` and `"AO_xxx"` with your actual I/O tag names from the hardware configuration.

---

## Summary — Checklist for PLC Engineer

| # | Task | Where in TIA Portal | Done? |
|---|------|---------------------|-------|
| 1 | Create **UDT_ProcessStep** | PLC data types | ☐ |
| 2 | Create **UDT_Process** | PLC data types | ☐ |
| 3 | Create **DB1780** with `Optimized Access = FALSE` | Program blocks → Data blocks | ☐ |
| 4 | **Record byte offsets** from DB1780 view | DB1780 → monitor tab | ☐ |
| 5 | Create **FB1780** (copy SCL code above) | Program blocks → Function blocks | ☐ |
| 6 | Call **FB1780** in **OB1** with correct I/O mappings | Main [OB1] | ☐ |
| 7 | **Compile** all blocks | Build → Compile | ☐ |
| 8 | **Download** to PLC | Online → Download to device | ☐ |
| 9 | **Test** with watch table: write StartCmd=TRUE, watch PLC_State change | Watch table | ☐ |
| 10 | **Give byte offset table** to the Node-RED engineer | Document | ☐ |

---

## How to Test in TIA Portal (Before Connecting Node-RED)

### Test 1: Manual Recipe Load
1. Open DB1780 in **monitor mode**
2. Manually write some test values:
   - `BatchID = "TEST-001"`
   - `ProcessCount = 1`
   - `Processes[0].ProcessActive = TRUE`
   - `Processes[0].StepCount = 2`
   - `Processes[0].Steps[0].StepTime = 10` (10 seconds)
   - `Processes[0].Steps[0].StepActive = TRUE`
   - `Processes[0].Steps[0].AgitatorRPM = 1000`
   - `Processes[0].Steps[1].StepTime = 5`
   - `Processes[0].Steps[1].StepActive = TRUE`
   - `RecipeReady = TRUE`

### Test 2: Start Batch
1. Write `StartCmd = TRUE`
2. Watch `PLC_State` change from `0` → `1` (Executing)
3. Watch `Step_Timer_Act` count down from `10`
4. After 10 seconds: `PLC_State` should change to `2` (WaitConfirm)
5. `Step_Done = TRUE`

### Test 3: Confirm Step
1. Write `Confirm_Phase = Active_Phase` (copy the value)
2. Write `Confirm_SubStep = Active_SubStep` (copy the value)
3. Write `Confirm_Step = TRUE`
4. Watch `PLC_State` change from `2` → `1` (back to Executing)
5. `Current_Step` should increment

### Test 4: Batch Complete
1. Repeat confirm for Step 2
2. After last step confirmed: `PLC_State = 4` (Done)
3. `Batch_Complete = TRUE`
4. All SP outputs = 0

### Test 5: Heartbeat Watchdog
1. Toggle `PC_Heartbeat` every 1 second
2. Stop toggling
3. After 5 seconds: `Error_Code = 1`
4. PLC should continue running (not stop)
