# Large Recipe Transfer Protocol Concept

> **Purpose:** To explain the step-by-step S7 logic for safely transferring massive SKUs (e.g., up to 32 Phases) from the App to the PLC without hitting hardware buffer limits.

---

## 1. The Hardware Limitation

The `DB1780_RecipeData` datablock is very large (about **29 KB**). However, the Siemens S7-1200 hardware protocol has a "PDU Size Limit" (Protocol Data Unit), meaning it can physically only accept about **240 bytes of data per single write request** at the lowest level.

If we attempted to send all 32 Phases in one single JSON command to `node-red-contrib-s7`, the node would buffer overflow and crash. 

## 2. The Solution: Dynamic Chunking

By breaking the recipe down so that the Node-RED logic writes **"One Step at a time"**, the network traffic stays perfectly stable. 

A single `UDT_ProcessStep` is about 100 bytes, which perfectly fits inside a single, fast S7 packet. With a ~15-20ms delay between writes, a massive 250-step recipe takes exactly **4 to 5 seconds** to transfer safely with zero data loss.

---

## 3. The Step-by-Step Transfer Queue (Node-RED logic)

Imagine FastAPI sends a huge recipe with **32 Phases** to Node-RED. Node-RED will build an array of write commands (a queue) and send them sequentially to the S7 node.

### 📍 Stage 1: PREPARE (Lock the PLC)
Node-RED sends the first commands to secure the machine, ensuring no operator can start the sequence while data is downloading.

```javascript
// Send command 1 & 2
Write -> Variable: "DB1780,X120.0" (RecipeLoading)  Value: TRUE
Write -> Variable: "DB1780,X121.0" (RecipeReady)    Value: FALSE
```

### 📍 Stage 2: TRANSFER HEADER (Basic Info)
Node-RED writes the basic string and float data for the batch header.

```javascript
// Send commands 3 through 10
Write -> Variable: "DB1780,S0.30"    (PlanID)       Value: "P260309-01-01"
Write -> Variable: "DB1780,S32.20"   (BatchID)      Value: "P260309-01-01-001"
Write -> Variable: "DB1780,S54.20"   (SkuID)        Value: "SFGFSU4200"
Write -> Variable: "DB1780,REAL110"  (BatchSize)    Value: 4200.0
Write -> Variable: "DB1780,INT114"   (ProcessCount) Value: 32  <-- Max phases!
Write -> Variable: "DB1780,DINT122"  (CRC_App)      Value: 3408960
```

### 📍 Stage 3: TRANSFER PROCESSES (The Big Loop)
Because this is the biggest SKU, Node-RED runs a `for` loop from Phase 0 to Phase 31. Instead of writing every tiny integer one-by-one (which would take 5,000 writes), Node-RED writes a **whole Step at a time**. 

```javascript
// ---- Phase 0 (Process 10) ----
// Write Process Metadata
Write -> Variable: "DB1780,INT356"  (Processes[0].ProcessNo) Value: 10
Write -> Variable: "DB1780,INT358"  (Processes[0].PhaseID)   Value: 401
Write -> Variable: "DB1780,INT360"  (Processes[0].StepCount) Value: 4

// Write Step 0
Write -> Variable: "DB1780,INT364"  (Processes[0].Steps[0].StepNo)       Value: 10
Write -> Variable: "DB1780,INT366"  (Processes[0].Steps[0].ActionCode)   Value: 10010
Write -> Variable: "DB1780,S368.25" (Processes[0].Steps[0].ReCode)       Value: "RO-Water"
Write -> Variable: "DB1780,REAL418" (Processes[0].Steps[0].Require)      Value: 1200.0
Write -> Variable: "DB1780,REAL430" (Processes[0].Steps[0].Temperature)  Value: 85.0
// ... NodeRED continues for all properties of Step 0

// Write Step 1
Write -> Variable: "DB1780,INT464"  (Processes[0].Steps[1].StepNo)       Value: 20
Write -> Variable: "DB1780,INT466"  (Processes[0].Steps[1].ActionCode)   Value: 21010
// ... NodeRED continues for all properties of Step 1

// ---- Phase 1 (Process 20) ----
Write -> Variable: "DB1780,INT1156" (Processes[1].ProcessNo) Value: 20
// ... Writes all steps for Phase 1 ...

// ... (Loops all the way down to Phase 31) ...
```

### 📍 Stage 4: VERIFY AND ACTIVATE
Once the loop finishes (after about 3-4 seconds of rapid-fire S7 messages), Node-RED unlocks the PLC.

Because we sent it in over 150 pieces, what happens if the Wi-Fi drops and a piece gets lost? Node-RED relies on the `CRC_App` variable sent in Stage 2.

```javascript
// Release the lock
Write -> Variable: "DB1780,X120.0" (RecipeLoading)  Value: FALSE

// The PLC now automatically runs FC_CalcChecksum inside its own processor.
// It calculates the exact sum of all 250 steps it received.
// Node-RED polls the status to check if it worked:
Read  <- Variable: "DB1780,X126.0" (CRC_Match)      Result: TRUE!

// Since it matched perfectly, Node-RED gives the final green light
Write -> Variable: "DB1780,X121.0" (RecipeReady)    Value: TRUE
```

The UI turns green, and the operator is now allowed to press START. We are 100% certain that no data was dropped.
