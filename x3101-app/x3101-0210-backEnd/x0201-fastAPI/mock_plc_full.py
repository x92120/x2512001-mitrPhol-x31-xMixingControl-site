"""
Full Production Simulator — mock_plc_full.py
=============================================
Simulates a COMPLETE production run from Step 1 to Final Step
using REAL data from the database. Publishes MQTT telemetry
exactly as a real PLC would, so the Nuxt V2 page can track it.

Usage:
    python3 mock_plc_full.py
"""

import paho.mqtt.client as mqtt
import json
import time
import random
import sys
import os

# Add parent path for imports
sys.path.insert(0, os.path.dirname(__file__))

from database import SessionLocal
import models
import re as regex

# ── Configuration ──
BROKER = "localhost"
PORT = 1883
PLANT_ID = "01"
STEP_INTERVAL = 3  # seconds between steps (adjust for faster/slower demo)

# MQTT Topics (must match what useMQTT composable subscribes to)
STATUS_TOPIC = f"mixing/plant/{int(PLANT_ID)}/status"
READ_TOPIC = f"MIX-{PLANT_ID}-READ"
PUT_TOPIC = f"MIX-{PLANT_ID}-PUT"


def parse_phase_num(val):
    """Parse phase number like 'p0010' → 'p0010' (keep as-is for matching)."""
    return str(val or '0').strip()


def parse_int(val, default=0):
    s = str(val or '0').strip()
    s = regex.sub(r'^[a-zA-Z]+', '', s)
    return int(s) if s else default


def load_production_steps():
    """Load real steps from the database for the first active batch."""
    db = SessionLocal()
    try:
        batch = db.query(models.ProductionBatch).first()
        if not batch:
            print("❌ No production batch found in database!")
            return None, []

        plan = db.query(models.ProductionPlan).filter(
            models.ProductionPlan.id == batch.plan_id
        ).first()
        if not plan:
            print(f"❌ No plan found for batch {batch.batch_id}")
            return None, []

        steps = db.query(models.SkuStep).filter(
            models.SkuStep.sku_id == plan.sku_id
        ).all()

        # Sort by phase then sub_step
        sorted_steps = sorted(steps, key=lambda s: (
            parse_int(s.phase_number),
            s.sub_step or 0
        ))

        batch_info = {
            "batch_id": batch.batch_id,
            "plan_id": plan.plan_id,
            "sku_id": plan.sku_id,
            "sku_name": plan.sku_name or "",
            "batch_size": float(batch.batch_size or 0),
            "total_steps": len(sorted_steps),
        }

        step_list = []
        for s in sorted_steps:
            step_list.append({
                "phase_number": str(s.phase_number or "0"),
                "sub_step": s.sub_step or 0,
                "action_code": str(s.action_code or ""),
                "action_description": s.action_description or s.action or "-",
                "re_code": s.re_code or "-",
                "require": float(s.require or 0),
                "temperature": float(s.temperature or 0),
                "agitator_rpm": float(s.agitator_rpm or 0),
                "high_shear_rpm": float(s.high_shear_rpm or 0),
                "step_time": int(s.step_time or 0),
                "brix_sp": float(s.brix_sp or 0),
                "ph_sp": float(s.ph_sp or 0),
            })

        return batch_info, step_list
    finally:
        db.close()


def on_connect(client, userdata, flags, rc):
    status = "OK" if rc == 0 else f"code {rc}"
    print(f"  ✅ MQTT Connected ({status})")


def simulate_full_production():
    """Run the full production simulation."""

    # ── Load real data ──
    print("=" * 60)
    print("  FULL PRODUCTION SIMULATOR (Mock PLC)")
    print("=" * 60)
    print()
    print("📊 Loading production data from database...")

    batch_info, steps = load_production_steps()
    if not batch_info or not steps:
        return

    print(f"  Batch:  {batch_info['batch_id']}")
    print(f"  Plan:   {batch_info['plan_id']}")
    print(f"  SKU:    {batch_info['sku_id']} — {batch_info['sku_name']}")
    print(f"  Steps:  {batch_info['total_steps']}")
    print()

    # ── Connect MQTT ──
    print("🔌 Connecting to MQTT broker...")
    client = mqtt.Client(client_id="Mock_PLC_FullSim")
    client.on_connect = on_connect

    try:
        client.connect(BROKER, PORT, 60)
        client.loop_start()
    except Exception as e:
        print(f"  ❌ Failed to connect to MQTT: {e}")
        print(f"     Make sure RabbitMQ/Mosquitto is running on port {PORT}")
        return

    time.sleep(1)  # Wait for connection

    # ── Publish initial batch info (like the PC does on Confirm Start) ──
    print()
    print("📋 Publishing batch info to PLC topic...")
    init_payload = {
        "watch_dog": 0,
        "plan_id": batch_info["plan_id"],
        "batch_id": batch_info["batch_id"],
        "sku_id": batch_info["sku_id"],
        "sku_name": f"{batch_info['sku_id']}-{batch_info['sku_name']}",
        "phase_id": "-",
        "PLC_State": 0,  # Idle
        "Current_Step": 0,
        "last_update": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    client.publish(READ_TOPIC, json.dumps(init_payload))
    client.publish(STATUS_TOPIC, json.dumps(init_payload))
    print(f"  ✅ Batch {batch_info['batch_id']} registered")

    print()
    print(f"🚀 Starting production in {STEP_INTERVAL} seconds...")
    print(f"   ({STEP_INTERVAL}s between each step for demo)")
    print()
    time.sleep(STEP_INTERVAL)

    # ── Walk through every step ──
    for i, step in enumerate(steps):
        step_num = i + 1
        is_manual = step["action_code"] in ("21010", "30020")
        is_last = (i == len(steps) - 1)

        # Build the status line
        action_tag = "🖐️  MANUAL" if is_manual else "⚙️  AUTO"
        phase_str = step["phase_number"]
        sub_str = step["sub_step"]

        print(f"─── Step {step_num}/{len(steps)} ── {action_tag} ───────────────")
        print(f"  Phase: {phase_str}  Sub-Step: {sub_str}")
        print(f"  Action: [{step['action_code']}] {step['action_description'][:45]}")
        if step["re_code"] != "-":
            print(f"  Material: {step['re_code']}")
        if step["temperature"] > 0:
            print(f"  Temp SP: {step['temperature']}°C")
        if step["step_time"] > 0:
            print(f"  Time: {step['step_time']} min")

        # ── Build MQTT telemetry payload ──
        # This is what the real PLC DB would contain
        telemetry = {
            # Identifiers
            "watchdog": random.randint(0, 100),
            "Batch_ID": batch_info["batch_id"],
            "Plan_ID": batch_info["plan_id"],
            "SKU_Name": f"{batch_info['sku_id']}-{batch_info['sku_name']}",

            # PLC State
            "PLC_State": 2 if is_manual else 1,  # 1=Run, 2=WaitManual
            "Current_Step": step_num,

            # Step identification (for Nuxt currentStepIndex matching)
            "Phase_ID": phase_str,
            "Step_ID": sub_str,
            "phase_id": phase_str,
            "step_id": sub_str,

            # Actuals (simulated)
            "Mixing_Tank_Volume": round(random.uniform(50, 200), 1),
            "Mixing_Tank_Temperature": round(
                step["temperature"] + random.uniform(-2, 2), 1
            ) if step["temperature"] > 0 else round(random.uniform(25, 30), 1),
            "MixingTank_Agitator_Speed": step["agitator_rpm"] or round(random.uniform(800, 1500), 0),
            "HighShare_Speed": step["high_shear_rpm"] or 0,
            "Hopper_Weight": round(step["require"] * random.uniform(0.98, 1.02), 2) if step["require"] > 0 else 0,

            # Step status
            "Step_Timer": step["step_time"] * 60 if step["step_time"] > 0 else 0,
            "last_update": time.strftime("%Y-%m-%dT%H:%M:%S"),

            # Step complete trigger
            "status": "STEP_COMPLETE",
            "step_no": step_num,
        }

        # Add Brix/pH if applicable
        if step["brix_sp"] > 0:
            telemetry["Brix"] = round(step["brix_sp"] + random.uniform(-0.5, 0.5), 2)
        if step["ph_sp"] > 0:
            telemetry["PH"] = round(step["ph_sp"] + random.uniform(-0.1, 0.1), 2)

        # ── Publish to all relevant topics ──
        client.publish(STATUS_TOPIC, json.dumps(telemetry))
        client.publish(READ_TOPIC, json.dumps(telemetry))

        state_str = "WAIT_MANUAL" if is_manual else "RUNNING"
        print(f"  📡 Published → PLC_State={telemetry['PLC_State']} ({state_str})")
        print(f"     Phase_ID={phase_str}, Step_ID={sub_str}")
        print()

        if not is_last:
            time.sleep(STEP_INTERVAL)

    # ── Batch Complete ──
    print("=" * 60)
    print("  🎉 BATCH COMPLETE!")
    print(f"  Batch: {batch_info['batch_id']}")
    print(f"  Total Steps Executed: {len(steps)}")
    print("=" * 60)

    complete_payload = {
        "watchdog": random.randint(0, 100),
        "Batch_ID": batch_info["batch_id"],
        "PLC_State": 4,  # Done
        "Current_Step": len(steps),
        "Batch_Complete": True,
        "last_update": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    client.publish(STATUS_TOPIC, json.dumps(complete_payload))
    client.publish(READ_TOPIC, json.dumps(complete_payload))

    time.sleep(2)
    client.loop_stop()
    client.disconnect()
    print("\n✅ Simulator disconnected. Done.")


if __name__ == "__main__":
    simulate_full_production()
