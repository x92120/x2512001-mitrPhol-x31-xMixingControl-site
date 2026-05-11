# PLC Integration Implementation Plan

This document outlines the step-by-step process for upgrading the current PC-driven mixing system to the new "PLC as State Master" architecture. It includes testing strategies for each phase to ensure the logic works flawlessly before deploying to the physical plant.

## Phase 1: Backend Foundation & Mocking
**Goal:** Prepare FastAPI to format PLC data, send it out, and listen for updates asynchronously.

*   **Step 1.1: Data Models:** Create Pydantic schemas in FastAPI that exactly match the `UDT_RecipeStep` and `DB_Recipe` structures.
*   **Step 1.2: Download Endpoint:** Implement `POST /api/batch/{id}/download-to-plc`. This will query `sku_steps`, format the 50-step array, and publish it to a RabbitMQ queue (or directly to Node-RED via HTTP).
*   **Step 1.3: RabbitMQ Consumer:** Build a background worker in FastAPI that listens to `plc.mixing.state` on RabbitMQ. When a message arrives (e.g., `{"Current_Step_Idx": 15, "PLC_State": 1}`), it updates `mixing_batch_step_log` in MySQL.
*   **Testing Design (Phase 1):** 
    *   *How to Test:* We will write a small Python "PLC Simulator" script.
    *   *Test Flow:* The simulator will listen to the download endpoint, receive the 35 steps, and then use a `for` loop to publish fake JSON state updates to RabbitMQ every 2 seconds. We will watch FastAPI successfully consume these messages and write them to the database.

---

## Phase 2: Frontend (Nuxt) Decoupling & WebSockets
**Goal:** Remove local timers from the UI and make the frontend react instantly to backend events.

*   **Step 2.1: Clean up UI Logic:** Remove all `setTimeout` or manual "Next Step" timer logic from `x61-MixingControl.vue` (except for manual ingredient scan steps).
*   **Step 2.2: WebSocket Setup:** Add a WebSocket or Server-Sent Events (SSE) route in FastAPI that broadcasts the PLC state to the Nuxt frontend.
*   **Step 2.3: UI Reactivity:** Update Pinia stores so that when a WebSocket message is received containing a new `Current_Step_Idx`, the UI automatically scrolls to and highlights the new step.
*   **Step 2.4: Recovery on Mount:** When the page loads (`onMounted`), fetch the current state from FastAPI to instantly resume the view.
*   **Testing Design (Phase 2):**
    *   *How to Test:* We will use our Phase 1 Python Simulator to fire events. We will open the browser, start the simulated batch, and visually confirm the UI steps through the process automatically without user clicks. We will then forcefully refresh the browser (F5) to ensure it recovers and highlights the correct active step upon reload.

---

## Phase 3: Heartbeat & Node-RED Integration
**Goal:** Implement safety mechanisms and connect to the real PLC layer.

*   **Step 3.1: PC Heartbeat:** Create a loop in FastAPI that publishes a `Heartbeat: TRUE/FALSE` toggle to RabbitMQ every 1 second.
*   **Step 3.2: Node-RED Configuration:** Configure the `node-red-contrib-s7` nodes to map the RabbitMQ JSON payloads directly to the Siemens S7 `DB_Recipe` byte offsets.
*   **Testing Design (Phase 3):**
    *   *How to Test:* **The "Pull the Plug" Test.** We will run a batch using the simulator or a test PLC. At Step 15, we will manually kill the FastAPI server. The PLC should hold state. We then restart FastAPI and verify it reconnects, reads Step 15, and resumes flawlessly.
