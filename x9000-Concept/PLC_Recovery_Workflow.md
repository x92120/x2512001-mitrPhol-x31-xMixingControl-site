# PLC & PC Concept and Recovery Workflow
*Architecture for seamless recovery from App or PC shutdown during mixing execution.*

To handle scenarios where the App or Computer shuts down abruptly while maintaining the ability to seamlessly recover, the best approach is the **"PLC as Executor, PC as Supervisor"** concept.

Once the production starts, the PLC must not rely on the PC to feed it instructions step-by-step. Instead, the PLC holds the recipe and manages the state machine, while the PC just watches and logs.

## 1. The Concept (PLC as State Master)
* **Pre-load the Recipe:** The entire recipe (or up to 50 steps) is downloaded into the PLC's `DB_Recipe` *before* the batch officially starts.
* **PLC Manages the Sequence:** The PLC uses an internal variable (e.g., `Current_Step_Idx`) to track where it is. It executes Step 1, finishes it, and automatically moves to Step 2 without asking the PC.
* **PC is just a Viewer/Logger:** The App continuously polls the PLC to read `Current_Step_Idx` and logs the actual values (actual temp, time taken, etc.) to the database.
* **Resume Capability:** Because the PLC knows the `Batch_ID` and the `Current_Step_Idx`, if the PC reboots, the PC simply asks the PLC: *"What Batch are you running, and what step are you on?"* and immediately syncs its UI back to reality.

---

## 2. Required Updates to your Data Block Header
To make recovery work, you need to add a few synchronization variables to your `DB_Recipe` header:

```pascal
      // Header Information
      Batch_ID         : STRING[20];   // Critical: Links PLC memory to your Database Batch
      SKU_ID           : STRING[20];   
      Total_Steps      : INT;          
      Current_Step_Idx : INT;          // PLC updates this as it moves forward
      
      // Handshake & Status
      Command_Start    : BOOL;         // PC tells PLC to Start
      Command_Pause    : BOOL;         // PC tells PLC to Pause
      PC_Heartbeat     : BOOL;         // Toggles every 1s. If PLC doesn't see toggle, PC is dead.
      PLC_State        : INT;          // 0=Idle, 1=Running, 2=Waiting for Manual, 3=Paused, 4=Done
```

---

## 3. Normal Workflow (No Crashes)
1. **Download:** Operator selects a Batch. The App writes the `Batch_ID` and the array of up to 50 steps to the PLC.
2. **Start:** App sends `Command_Start = TRUE`. 
3. **Execution:** PLC reads `Steps[Current_Step_Idx]`, sets Agitator, High Shear, and Temp. It waits for the `Step_Time` to finish.
4. **Transition:** When the time is up, PLC increments `Current_Step_Idx += 1` and executes the next step automatically.
5. **Logging:** The App notices `Current_Step_Idx` changed, so it records the completion of the previous step into your `mixing_batch_step_log` table.

---

## 4. Recovery Workflow (App / Computer Crashes & Restarts)

**Scenario:** The PC dies during Step 15.

1. **PLC Reaction (PC_Heartbeat fails):**
   * The PLC detects the `PC_Heartbeat` stopped toggling. 
   * **If the step is automatic** (e.g., mixing for 5 minutes), the PLC *continues* running the step to avoid ruining the product.
   * **If the step requires manual scanning** (like Action 21010 "Manual Add"), the PLC safely goes into a `Waiting` state (keeping agitator on, but timer paused) because the operator needs the PC scanner to continue.

2. **PC Reboots & App Starts:**
   * The App connects to the PLC and reads the `Batch_ID` and `Current_Step_Idx`.
   * **App Logic:** "Ah, the PLC says it is running Batch `B20260510-01` at Step `15`."

3. **Syncing the Database:**
   * The App checks its database for `B20260510-01`. 
   * It sees the batch status is still `In Progress`.
   * It sees logs up to Step 14. It knows Step 15 is currently active.

4. **Resume UI:** 
   * The App instantly routes the operator to the Mixing Control screen for that Batch, highlights Step 15 as "Running", and resumes polling data. **Recovery Complete without any operator input.**

---

## 5. PLC Communication Protocol: The Best Choice
Since your architecture already utilizes **Node-RED** and **RabbitMQ**, the absolute most robust way to communicate with the PLC is to decouple the PC from the PLC physically using Node-RED as middleware.

**Option A: S7 Protocol via Node-RED (Recommended for Siemens S7-1200/1500)**
*   Use the `node-red-contrib-s7` node.
*   **Why:** It natively reads/writes to the Data Block (DB) based on absolute offsets (e.g., `DB1,X0.0`) without requiring any special code or licenses on the PLC side. It is extremely fast and lightweight.

**Option B: OPC UA (Recommended if PLC supports it natively)**
*   Use `node-red-contrib-opcua`.
*   **Why:** Tag-based and highly standardized. If the PLC tags move, OPC UA doesn't break. 

**The Ideal Communication Flow:**
1.  **Polling:** Node-RED connects to the PLC and polls the `DB_Recipe` header every 500ms.
2.  **Publishing:** If `Current_Step_Idx` or `PLC_State` changes, Node-RED publishes a JSON message to a **RabbitMQ** topic (e.g., `plc.mixing.state`).
3.  **Consuming:** FastAPI listens to RabbitMQ, logs the step completion securely into MySQL (`mixing_batch_step_log`), and broadcasts the live state to Nuxt.

---

## 6. Required Changes to Existing Applications

### Backend (FastAPI) Updates
1.  **Remove State-Machine Logic:** Remove any Python logic that says *"Wait 5 minutes then trigger the next step"*. FastAPI must become stateless; it only reacts to events emitted by the PLC via RabbitMQ.
2.  **Add Download Endpoint:** Create a `POST /api/batch/{id}/download-to-plc` endpoint. This query formats the 50-step array and sends it to Node-RED to write to the PLC `DB_Recipe`.
3.  **RabbitMQ Consumer Worker:** Create a background worker in FastAPI to consume PLC state changes from RabbitMQ and update the MySQL database instantly.

### Frontend (Nuxt) Updates
1.  **Make UI Stateless:** The UI must stop driving the process. Remove the manual "Next Step" buttons for any automated mixing/heating steps.
2.  **WebSocket / SSE Integration:** The frontend should connect to FastAPI via WebSocket. When the PLC moves to Step 15, the frontend instantly receives the event and visually highlights Step 15 in the UI.
3.  **Recovery on Mount (`onMounted`):** When the operator navigates to the Mixing Control page, the code should immediately fetch the current `PLC_State` and `Current_Step_Idx`. If the batch is already running, the UI simply jumps to that step and resumes monitoring.
4.  **Heartbeat Signal:** The Nuxt frontend (or FastAPI) must implement a loop that toggles the `PC_Heartbeat` bit in the PLC every 1-2 seconds so the PLC knows the PC is alive.
