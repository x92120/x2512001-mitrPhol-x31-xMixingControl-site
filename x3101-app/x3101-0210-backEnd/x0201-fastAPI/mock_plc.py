import paho.mqtt.client as mqtt
import json
import time
import random
import sys

# Configuration
BROKER = "localhost"
PORT = 1883
PLANT_ID = "01"

# The topic that the Nuxt frontend listens to for telemetry
# The `useMQTT` composable typically expects plant data under `mixing/plant/1/status` or similar.
# In Nuxt: `topic === MIX-01-READ` or `mixing/plant/1/telemetry`
TELEMETRY_TOPIC = f"mixing/plant/{int(PLANT_ID)}/status" 

# Steps to simulate
SIM_STEPS = [
    {"phase": "20", "step": 1, "desc": "Start Program"},
    {"phase": "20", "step": 2, "desc": "Fill Major Ingredient"},
    {"phase": "20", "step": 3, "desc": "Preblending"},
    {"phase": "30", "step": 1, "desc": "First Confirm"},
    {"phase": "30", "step": 2, "desc": "Pre Heats"}
]

def on_connect(client, userdata, flags, rc):
    print(f"✅ Connected to MQTT Broker at {BROKER}:{PORT} with result code {rc}")

def simulate_plc():
    client = mqtt.Client(client_id="Mock_PLC_V2")
    client.on_connect = on_connect
    
    try:
        client.connect(BROKER, PORT, 60)
        client.loop_start()
    except Exception as e:
        print(f"❌ Failed to connect to MQTT: {e}")
        return

    print("🚀 Starting PLC Simulation... Wait 5 seconds")
    time.sleep(5)

    for i, step in enumerate(SIM_STEPS):
        print(f"\n--- Simulating PLC moving to Phase {step['phase']} Step {step['step']} ({step['desc']}) ---")
        
        # Telemetry Payload matching what Nuxt expects to update `plantData`
        payload = {
            "watchdog": random.randint(0, 100),
            "PLC_State": 1, # 1=Run
            "Current_Step": i + 2, 
            "Phase_ID": step["phase"],
            "Step_ID": step["step"],
            "Mixing_Tank_Volume": random.uniform(100, 150),
            "Mixing_Tank_Temperature": random.uniform(60, 65),
            "MixingTank_Agitator_Speed": 1500,
            "status": "STEP_COMPLETE", # This triggers the UI popup in Nuxt
            "step_no": i + 2
        }

        # Publish the state
        client.publish(TELEMETRY_TOPIC, json.dumps(payload))
        
        # Publish to the specific READ topic for the handshake
        client.publish(f"MIX-{PLANT_ID}-READ", json.dumps(payload))

        print(f"📡 Published payload: {json.dumps(payload, indent=2)}")
        
        # Wait 5 seconds before next step
        print("⏳ Waiting 5 seconds...")
        time.sleep(5)

    print("\n✅ Simulation Complete. PLC State = END")
    client.loop_stop()
    client.disconnect()

if __name__ == "__main__":
    simulate_plc()
