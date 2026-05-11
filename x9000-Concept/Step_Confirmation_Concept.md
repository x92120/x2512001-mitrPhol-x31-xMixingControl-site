# Step Confirmation Concept — Operator Must Confirm Every Step

## The Problem
In the current "full auto" design, the PLC auto-advances after timer/condition is met. 
But in real food manufacturing, the **operator must visually verify** each step is actually done 
before moving forward (e.g., "Is the sugar fully dissolved?", "Did the temperature reach 83°C?").

---

## The New Workflow: "Execute → Hold → Confirm → Advance"

```
┌─────────┐     ┌──────────────┐     ┌──────────────┐     ┌─────────────┐
│  PLC    │     │   PLC        │     │  Frontend    │     │    PLC      │
│ Execute │────►│ Step Done    │────►│ Operator     │────►│ Advance to  │
│ Step N  │     │ HOLD & Wait  │     │ Clicks       │     │ Step N+1    │
│         │     │ for Confirm  │     │ "CONFIRM ✅" │     │             │
└─────────┘     └──────────────┘     └──────────────┘     └─────────────┘
```

### PLC State Machine (Updated)

```
State 0: IDLE          → Waiting for recipe download + Start command
State 1: EXECUTING     → Running current step (timer counting, outputs ON)
State 2: WAIT_CONFIRM  → Step finished, holding outputs, waiting for operator
State 3: PAUSED        → Operator paused the batch
State 4: DONE          → All steps complete
State 9: ERROR         → Fault condition
```

**Key Change:** After every step completes, PLC goes to **State 2 (WAIT_CONFIRM)** 
instead of directly advancing. The agitator/temperature HOLD at current setpoint 
while waiting, so the product is safe.

---

## Data Block Updates (DB1780)

Add these fields to the header:

```pascal
// ── Confirmation Handshake ──
Step_Done          : Bool;    // PLC sets TRUE when step execution is finished
Confirm_Step       : Bool;    // PC sets TRUE to acknowledge and advance
Confirm_Phase_ID   : String[10];  // PC echoes back which phase it's confirming
Confirm_Step_ID    : Int;         // PC echoes back which step it's confirming
```

### PLC Logic Change (in FB1780):

```pascal
// After step timer/condition is met:
IF step_finished THEN
    "DB_RecipeData".Step_Done := TRUE;
    "DB_RecipeData".PLC_State := 2;  // WAIT_CONFIRM
    // DO NOT advance — hold current outputs
    // Agitator keeps running, temperature maintains
END_IF;

// When PC confirms:
IF "DB_RecipeData".Confirm_Step AND "DB_RecipeData".PLC_State = 2 THEN
    // Verify the confirmation matches current step (safety!)
    IF "DB_RecipeData".Confirm_Phase_ID = current_phase 
       AND "DB_RecipeData".Confirm_Step_ID = current_sub_step THEN
        
        // Reset flags
        "DB_RecipeData".Step_Done := FALSE;
        "DB_RecipeData".Confirm_Step := FALSE;
        
        // ADVANCE to next step
        advance_to_next_step();
        "DB_RecipeData".PLC_State := 1;  // Back to EXECUTING
    END_IF;
END_IF;
```

---

## Frontend Changes (x62-MixingControlV2.vue)

### What the Operator Sees:

```
┌────────────────────────────────────────────────────────┐
│ Step 5/13 — Phase p0030, Sub-Step 10                   │
│ Action: [20010] Dissolve Ingredient                    │
│ Material: Potassium Sorbate                            │
│                                                        │
│ ┌─────────────────────────────────────────────┐        │
│ │  ✅ STEP EXECUTION COMPLETE                 │        │
│ │                                              │        │
│ │  Temperature:  60.2°C / 60.0°C  ✅          │        │
│ │  Agitator:     1500 RPM         ✅          │        │
│ │  Duration:     5:00 / 5:00      ✅          │        │
│ │                                              │        │
│ │  ┌──────────────────────────────────────┐   │        │
│ │  │  🟢 CONFIRM STEP DONE & ADVANCE     │   │        │
│ │  └──────────────────────────────────────┘   │        │
│ └─────────────────────────────────────────────┘        │
└────────────────────────────────────────────────────────┘
```

### Button Behavior:

1. **Button is DISABLED** while `PLC_State = 1` (Executing) — the step is still running
2. **Button turns GREEN** when `PLC_State = 2` (Wait_Confirm) — step is done, waiting for operator
3. **Operator clicks** → Frontend publishes MQTT:
   ```json
   {
     "Confirm_Step": true,
     "Confirm_Phase_ID": "p0030",
     "Confirm_Step_ID": 10,
     "timestamp": "2026-05-10T17:55:00"
   }
   ```
4. PLC receives → validates → advances → `PLC_State` goes back to `1`
5. Frontend sees the state change and the next step starts highlighting

---

## MQTT Message Flow

### Step Execution (PLC → Frontend):
```
Topic: mixing/plant/1/status
{
  "PLC_State": 1,           ← Executing
  "Phase_ID": "p0030",
  "Step_ID": 10,
  "Step_Done": false,
  "Step_Timer": 245          ← Countdown
}
```

### Step Ready for Confirm (PLC → Frontend):
```
Topic: mixing/plant/1/status
{
  "PLC_State": 2,           ← Wait Confirm
  "Phase_ID": "p0030",
  "Step_ID": 10,
  "Step_Done": true,         ← Step finished!
  "Step_Timer": 0
}
```

### Operator Confirms (Frontend → PLC):
```
Topic: mixing/plant/1/step_confirm
{
  "Confirm_Step": true,
  "Confirm_Phase_ID": "p0030",
  "Confirm_Step_ID": 10
}
```

### PLC Advances (PLC → Frontend):
```
Topic: mixing/plant/1/status
{
  "PLC_State": 1,           ← Back to Executing
  "Phase_ID": "p0030",
  "Step_ID": 20,            ← Next step!
  "Step_Done": false,
  "Step_Timer": 300
}
```

---

## Safety Rules

| Rule | Description |
|------|-------------|
| **Phase/Step Echo** | Frontend MUST echo back which Phase+Step it's confirming. PLC rejects if mismatch. |
| **Double-click Guard** | Frontend disables the confirm button for 2 seconds after click to prevent double-advance. |
| **Heartbeat Still Active** | If PC_Heartbeat is lost while in WAIT_CONFIRM, PLC holds position indefinitely (safe state). |
| **Timeout Warning** | If WAIT_CONFIRM exceeds 10 minutes, PLC can trigger a warning alarm (but does NOT auto-advance). |
| **Manual Steps** | For ActionCode 21010 (Manual Add), the confirm button serves double duty: operator scans the ingredient AND confirms. |

---

## Summary of Changes Required

| Layer | What to Change |
|-------|---------------|
| **PLC DB1780** | Add `Step_Done`, `Confirm_Step`, `Confirm_Phase_ID`, `Confirm_Step_ID` fields |
| **PLC FB1780** | After step done → set State=2, hold outputs. On Confirm → validate → advance |
| **Node-RED** | Add S7-Out node to write `Confirm_Step` + IDs when MQTT confirm arrives |
| **Frontend** | Add "Confirm Step Done" button that enables only when `PLC_State = 2` |
| **Mock Simulator** | Update to wait for confirm MQTT message before advancing |
