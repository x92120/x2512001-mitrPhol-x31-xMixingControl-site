# Node-RED Implementation Guide

> **For:** System Integrator / Middleware Engineer  
> **Role:** Bridge between FastAPI/RabbitMQ and the Siemens S7 PLC  
> **Required Nodes:** `node-red-contrib-s7`, `node-red-contrib-amqp`

---

## Architecture Overview

Node-RED acts as a **Stateless Bridge**. It holds no business logic; it merely translates protocols (HTTP/AMQP ↔ S7 Comm).

You need to build **4 independent flows** in Node-RED:

```
1. Telemetry Polling      (PLC → RabbitMQ)
2. Command & Heartbeat    (RabbitMQ → PLC)
3. Step Confirmation      (RabbitMQ → PLC)
4. Recipe Transfer        (HTTP POST → PLC)
```

---

## 1. Prerequisites

1. Install the required palettes in Node-RED:
   - `node-red-contrib-s7` (For Siemens S7 communication)
   - `node-red-contrib-amqp` (For RabbitMQ integration)
2. Configure your **S7 Endpoint**:
   - PLC IP Address (e.g., `192.168.1.10`)
   - Port: `102`
   - Rack: `0`, Slot: `1` (for S7-1200/1500)
3. Configure your **AMQP Broker**:
   - Host: `localhost` (or IP of your RabbitMQ container)
   - Port: `5672`
   - Credentials (if any)

---

## Flow 1: Telemetry Polling (PLC → RabbitMQ)

**Purpose:** Read the live status and actual values from the PLC every 500ms and publish them to MQTT so the UI can update.

### Flow Structure
`[S7 In Node] ──► [Function: Format JSON] ──► [Filter: Report by Exception] ──► [AMQP Out Node]`

### S7 In Node Configuration
- Mode: **All variables**
- Poll Rate: **500 ms**
- Variables to Read (Ensure you get the exact byte offsets from TIA Portal DB1780!):
  - `PLC_State` (Int)
  - `Current_Process` (Int)
  - `Current_Step` (Int)
  - `Step_Done` (Bool)
  - `Batch_Complete` (Bool)
  - `Active_Phase` (String[10])
  - `Active_SubStep` (Int)
  - `Step_Timer_Act` (Int)
  - `MixTank_Temp_Act` (Real)
  - `Agitator_RPM_Act` (Real)
  ... (include all fields from DB1780 Section C & D)

### Function Node: Format JSON
```javascript
// Build the payload expected by the Nuxt UI
msg.payload = {
    "PLC_State": msg.payload.PLC_State,
    "Phase_ID": msg.payload.Active_Phase.replace(/\0/g, '').trim(),
    "Step_ID": msg.payload.Active_SubStep,
    "Step_Done": msg.payload.Step_Done,
    "Step_Timer": msg.payload.Step_Timer_Act,
    "Mixing_Tank_Temperature": msg.payload.MixTank_Temp_Act,
    "MixingTank_Agitator_Speed": msg.payload.Agitator_RPM_Act,
    "Batch_Complete": msg.payload.Batch_Complete,
    "last_update": new Date().toISOString()
};
return msg;
```

### Report by Exception Node (Filter)
- Use a `rbe` node (Report by Exception) to block messages unless the values have actually changed. This prevents flooding the AMQP broker and the browser UI with redundant messages every 500ms.

### AMQP Out Node
- Exchange: `amq.topic`
- Routing Key / Topic: `mixing/plant/1/status`
- Payload: `msg.payload` (JSON)

---

## Flow 2: Command & Heartbeat (RabbitMQ → PLC)

**Purpose:** Pass high-level commands (START, PAUSE, ABORT) and the 1-second watchdog heartbeat from the UI to the PLC.

### Flow Structure
`[AMQP In Node] ──► [Switch: Route Command] ──► [Function: Map to S7] ──► [S7 Out Node]`

### AMQP In Node
- Exchange: `amq.topic`
- Topic: `mixing/plant/1/cmd`

### Function Node
```javascript
const cmd = msg.payload;

// Map MQTT json payload to S7 variable names
if (cmd.command === 'START') {
    return { payload: { "StartCmd": true } };
} else if (cmd.command === 'PAUSE') {
    return { payload: { "PauseCmd": true } };
} else if (cmd.command === 'ABORT') {
    return { payload: { "AbortCmd": true } };
} else if (cmd.command === 'HEARTBEAT') {
    // UI toggles this bit every 1s
    return { payload: { "PC_Heartbeat": cmd.value } };
}
```

---

## Flow 3: Step Confirmation (RabbitMQ → PLC)

**Purpose:** When the operator clicks "CONFIRM ✅" on the UI, Node-RED writes the confirmation flags safely back to the PLC.

### Flow Structure
`[AMQP In Node] ──► [Function: Map Echo] ──► [S7 Out Node]`

### AMQP In Node
- Topic: `mixing/plant/1/step_confirm`

### Function Node
```javascript
// The payload contains the echo verification variables
const confirm = msg.payload;

if (confirm.Confirm_Step === true) {
    // Write multiple variables to S7 simultaneously
    return {
        payload: {
            "Confirm_Phase": confirm.Confirm_Phase_ID,
            "Confirm_SubStep": confirm.Confirm_Step_ID,
            "Confirm_Step": true
        }
    };
}
return null;
```

---

## Flow 4: Recipe Transfer (HTTP POST → PLC)

**Purpose:** Handle the 29 KB JSON recipe sent by FastAPI, chunk it into S7 commands, and write it.

### Flow Structure
`[HTTP In (POST)] ──► [Function: Chunk Builder] ──► [S7 Out (Multiple)] ──► [HTTP Response]`

### HTTP In Node
- Method: `POST`
- URL: `/api/plc/write-recipe`

### Function Node: Chunk Builder
*Note: Due to the S7 PDU size limit (240 bytes), you cannot write the entire 29KB DB in one shot. Use the S7 node's dynamic variable addressing (`msg.variable` and `msg.payload`) inside a loop or sequence.*

```javascript
const recipe = msg.payload;
let msgs = []; // Array of S7 write commands

// 1. Lock PLC (RecipeLoading = TRUE)
msgs.push({ variable: "DB1780,X120.0", payload: true }); // Example offset for RecipeLoading
msgs.push({ variable: "DB1780,X121.0", payload: false }); // RecipeReady = FALSE

// 2. Write Header
msgs.push({ variable: "DB1780,S0.30", payload: recipe.Header.PlanID });
msgs.push({ variable: "DB1780,S32.20", payload: recipe.Header.BatchID });
msgs.push({ variable: "DB1780,DINT134", payload: recipe.Header.CRC }); // CRC_App

// 3. Loop through Processes & Steps
// (Use exact byte offsets calculated from TIA Portal)
// Example writing Step 0 of Process 0:
// msgs.push({ variable: "DB1780,INT256", payload: step.StepNo });
// msgs.push({ variable: "DB1780,INT258", payload: step.ActionCode });

// 4. Release Lock (RecipeLoading = FALSE)
msgs.push({ variable: "DB1780,X120.0", payload: false });

// Send the array of commands. You may need to use a Delay node or loop
// to ensure the S7 connection isn't overwhelmed.
return [msgs];
```

*Hint: If writing 145 chunks sequentially is too complex in raw JavaScript, consider using a Node-RED `Split` node coupled with a `Delay` node (rate limit: 1 msg per 20ms) feeding into a single S7 Out node configured for dynamic addressing.*

### HTTP Response Node
- Status: `200`
- Body: `{"status": "transfer_started"}`
