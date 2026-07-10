#!/usr/bin/env python3
"""
test_plc_fb.py — Test script for FB_MixingController
ทดสอบการสื่อสาร PLC ผ่าน DB1510/1512/1513

Usage:
    python3 test_plc_fb.py --plant 1 --step 2
    python3 test_plc_fb.py --plant 1 --monitor
    python3 test_plc_fb.py --plant 1 --abort
"""

import struct
import time
import sys
import os
import argparse

# ── Add path ──────────────────────────────────────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    import snap7
    from snap7.util import get_bool, set_bool, get_int, get_real
except ImportError:
    print("❌ snap7 not installed. Run: pip install python-snap7")
    sys.exit(1)

# ── Config ────────────────────────────────────────────────────────────────────
PLC_IP   = os.getenv("PLC_IP", "192.168.21.210")
PLC_RACK = int(os.getenv("PLC_RACK", "0"))
PLC_SLOT = int(os.getenv("PLC_SLOT", "1"))

# DB numbers per plant
DB_MAP = {
    1: {"cmd": 1510, "recipe": 1511, "tele": 1512, "shake": 1513, "actual": 1517},
    2: {"cmd": 1520, "recipe": 1521, "tele": 1522, "shake": 1523, "actual": 1527},
    3: {"cmd": 1530, "recipe": 1531, "tele": 1532, "shake": 1533, "actual": 1537},
}

# Step descriptions (0-28)
STEP_DESC = {
    0: "Stand By", 1: "Starting Program", 2: "Start Program",
    3: "Filling Major", 4: "Fill Major", 5: "Filling Major Done",
    6: "Fill Major Done", 7: "Preblending", 8: "Preblending",
    9: "Waiting First Confirm", 10: "First Confirm",
    11: "Pre Heating", 12: "Pre Heats",
    13: "Filling Minor", 14: "Fill Minor",
    15: "Second Heating", 16: "Second Heat",
    17: "Filling Third", 18: "Fill Third",
    19: "Pasteurizing", 20: "Pasteurizer",
    21: "Waiting QC Confirm", 22: "QC Confirm",
    23: "Preparing Transfer", 24: "Ready To Transfer",
    25: "Transferring", 26: "Transferring",
    27: "Ending STEP", 28: "End STEP"
}

PLC_STATE_DESC = {
    0: "Idle", 1: "Running", 2: "Hold/WaitConfirm",
    3: "Paused", 4: "Done", 9: "Error"
}

# ── Helpers ───────────────────────────────────────────────────────────────────
def pack_s7_string(s: str, max_len: int) -> bytes:
    s_bytes = s.encode('ascii', errors='replace')[:max_len]
    return struct.pack('BB', max_len, len(s_bytes)) + s_bytes.ljust(max_len, b'\x00')

def unpack_s7_string(data: bytes, offset: int, max_len: int) -> str:
    actual_len = data[offset + 1]
    return data[offset + 2: offset + 2 + actual_len].decode('ascii', errors='replace')

def connect_plc():
    client = snap7.client.Client()
    print(f"🔌 Connecting to PLC {PLC_IP} rack={PLC_RACK} slot={PLC_SLOT}...")
    client.connect(PLC_IP, PLC_RACK, PLC_SLOT)
    if client.get_connected():
        print("✅ PLC Connected!")
        return client
    else:
        print("❌ Connection failed!")
        sys.exit(1)

# ── DB1512: Read Telemetry ────────────────────────────────────────────────────
def read_telemetry(client, db_num: int) -> dict:
    data = bytes(client.db_read(db_num, 0, 28))
    watchdog     = struct.unpack_from('>h', data, 0)[0]
    plc_state    = struct.unpack_from('>h', data, 2)[0]
    current_step = struct.unpack_from('>h', data, 4)[0]
    step_timer   = struct.unpack_from('>h', data, 6)[0]
    mix_temp     = struct.unpack_from('>f', data, 8)[0]
    mix_weight   = struct.unpack_from('>f', data, 12)[0]
    agit_act     = struct.unpack_from('>f', data, 16)[0]
    hs_act       = struct.unpack_from('>f', data, 20)[0]
    hopper_wt    = struct.unpack_from('>f', data, 24)[0]
    return {
        "watchdog": watchdog, "plc_state": plc_state,
        "current_step": current_step, "step_timer": step_timer,
        "mix_temp": round(mix_temp, 1), "mix_weight": round(mix_weight, 1),
        "agit_act": round(agit_act, 1), "hs_act": round(hs_act, 1),
        "hopper_wt": round(hopper_wt, 1)
    }

# ── DB1513: Read Handshake ────────────────────────────────────────────────────
def read_handshake(client, db_num: int) -> dict:
    data = bytes(client.db_read(db_num, 0, 16))
    step_complete = bool(data[0] & 0x01)
    finished_step = struct.unpack_from('>h', data, 2)[0]
    end_temp      = struct.unpack_from('>f', data, 4)[0]
    end_weight    = struct.unpack_from('>f', data, 8)[0]
    error_flag    = bool(data[12] & 0x01)
    error_code    = struct.unpack_from('>h', data, 14)[0]
    return {
        "step_complete": step_complete, "finished_step": finished_step,
        "end_temp": round(end_temp, 1), "end_weight": round(end_weight, 1),
        "error_flag": error_flag, "error_code": error_code
    }

# ── DB1510: Write Step Command ────────────────────────────────────────────────
def write_step_cmd(client, db_num: int,
                   batch_id: str = "TEST-BATCH-01",
                   hmi_cmd: int = 0,
                   step_no: int = 0,
                   phase_id: str = "",
                   re_code: str = "",
                   target_wt: float = 0.0,
                   temp_sp: float = 0.0,
                   temp_low: float = 0.0,
                   temp_high: float = 100.0,
                   agit_sp: float = 0.0,
                   hs_sp: float = 0.0,
                   step_time: int = 0,
                   cmd_new_step: bool = False):
    payload = b""
    payload += pack_s7_string(batch_id, 20)       # +0   22 bytes
    payload += struct.pack('>h', hmi_cmd)          # +22   2 bytes
    payload += struct.pack('>h', step_no)          # +24   2 bytes
    payload += pack_s7_string(phase_id, 10)        # +26  12 bytes
    payload += pack_s7_string(re_code, 20)         # +38  22 bytes
    payload += struct.pack('>f', target_wt)        # +60   4 bytes
    payload += struct.pack('>f', temp_sp)          # +64   4 bytes
    payload += struct.pack('>f', temp_low)         # +68   4 bytes
    payload += struct.pack('>f', temp_high)        # +72   4 bytes
    payload += struct.pack('>f', agit_sp)          # +76   4 bytes
    payload += struct.pack('>f', hs_sp)            # +80   4 bytes
    payload += struct.pack('>h', step_time)        # +84   2 bytes
    payload += struct.pack('?', cmd_new_step)      # +86   1 byte
    payload += b'\x00'                             # +87   1 byte padding
    # Total = 88 bytes
    client.db_write(db_num, 0, bytearray(payload))
    print(f"✍️  DB{db_num} written: step={step_no} hmi={hmi_cmd} cmd_new={cmd_new_step}")

# ── Actions ───────────────────────────────────────────────────────────────────
def action_send_step(client, plant: int, step_no: int,
                     temp_sp: float = 60.0, agit: float = 80.0,
                     step_time: int = 0, batch_id: str = "TEST-BATCH-01"):
    dbs = DB_MAP[plant]
    step_name = STEP_DESC.get(step_no, "Unknown")
    print(f"\n📤 Plant {plant} → Step {step_no}: {step_name}")
    print(f"   Temp={temp_sp}°C  Agit={agit}rpm  Time={step_time}s")

    # 1. Set HMI_Command = 1 (START) first
    write_step_cmd(client, dbs["cmd"], batch_id=batch_id,
                   hmi_cmd=1, step_no=step_no,
                   temp_sp=temp_sp, agit_sp=agit,
                   step_time=step_time, cmd_new_step=False)
    time.sleep(0.3)

    # 2. Trigger Cmd_NewStep
    write_step_cmd(client, dbs["cmd"], batch_id=batch_id,
                   hmi_cmd=0, step_no=step_no,
                   temp_sp=temp_sp, agit_sp=agit,
                   step_time=step_time, cmd_new_step=True)
    print("   ✅ Cmd_NewStep sent")

def action_abort(client, plant: int):
    dbs = DB_MAP[plant]
    write_step_cmd(client, dbs["cmd"], hmi_cmd=3)
    print(f"🛑 Plant {plant} ABORT sent")

def action_monitor(client, plant: int, duration: int = 60):
    dbs = DB_MAP[plant]
    print(f"\n📡 Monitoring Plant {plant} for {duration}s... (Ctrl+C to stop)\n")
    print(f"{'Time':>6} | {'State':>12} | {'Step':>4} {'StepName':>22} | {'Timer':>5} | {'Temp':>6} | {'Weight':>7} | {'WD':>5}")
    print("-" * 90)

    start = time.time()
    prev_step = -1

    try:
        while time.time() - start < duration:
            t = read_telemetry(client, dbs["tele"])
            h = read_handshake(client, dbs["shake"])

            elapsed = int(time.time() - start)
            state_name = PLC_STATE_DESC.get(t["plc_state"], f"?{t['plc_state']}")
            step_name  = STEP_DESC.get(t["current_step"], "???")

            print(f"{elapsed:>6}s | {state_name:>12} | {t['current_step']:>4} {step_name:>22} "
                  f"| {t['step_timer']:>5}s | {t['mix_temp']:>5.1f}°C | {t['mix_weight']:>6.1f}kg"
                  f"| {t['watchdog']:>5}", end="")

            if h["step_complete"]:
                print(f"  🔔 STEP {h['finished_step']} COMPLETE! "
                      f"Temp={h['end_temp']}°C Weight={h['end_weight']}kg", end="")

            if t["current_step"] != prev_step:
                prev_step = t["current_step"]
                print(f"  ← NEW STEP", end="")

            print()
            time.sleep(1)

    except KeyboardInterrupt:
        print("\n⏹ Monitor stopped")

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description='Test FB_MixingController')
    parser.add_argument('--plant',  type=int, default=1, choices=[1,2,3])
    parser.add_argument('--step',   type=int, help='Send step number (0-28)')
    parser.add_argument('--temp',   type=float, default=60.0)
    parser.add_argument('--agit',   type=float, default=80.0)
    parser.add_argument('--time',   type=int, default=0, help='Step time (seconds)')
    parser.add_argument('--batch',  type=str, default='TEST-BATCH-01')
    parser.add_argument('--monitor',action='store_true', help='Monitor live telemetry')
    parser.add_argument('--abort',  action='store_true', help='Send ABORT command')
    parser.add_argument('--read',   action='store_true', help='Read current state once')
    parser.add_argument('--duration', type=int, default=120, help='Monitor duration (s)')
    args = parser.parse_args()

    client = connect_plc()

    try:
        if args.abort:
            action_abort(client, args.plant)

        elif args.step is not None:
            action_send_step(client, args.plant,
                             step_no=args.step,
                             temp_sp=args.temp,
                             agit=args.agit,
                             step_time=args.time,
                             batch_id=args.batch)
            if args.monitor:
                time.sleep(0.5)
                action_monitor(client, args.plant, args.duration)

        elif args.monitor:
            action_monitor(client, args.plant, args.duration)

        elif args.read:
            dbs = DB_MAP[args.plant]
            t = read_telemetry(client, dbs["tele"])
            h = read_handshake(client, dbs["shake"])
            print(f"\n── Plant {args.plant} State ──────────────────")
            print(f"  PLC State   : {t['plc_state']} ({PLC_STATE_DESC.get(t['plc_state'],'?')})")
            print(f"  Current Step: {t['current_step']} — {STEP_DESC.get(t['current_step'],'?')}")
            print(f"  Step Timer  : {t['step_timer']}s")
            print(f"  Temp        : {t['mix_temp']}°C")
            print(f"  Weight      : {t['mix_weight']} kg")
            print(f"  Agitator    : {t['agit_act']} RPM")
            print(f"  HighShear   : {t['hs_act']} RPM")
            print(f"  Hopper      : {t['hopper_wt']} kg")
            print(f"  Watchdog    : {t['watchdog']}")
            print(f"  Step Done   : {h['step_complete']} (Step {h['finished_step']})")
            if h['error_flag']:
                print(f"  ⚠️ Error    : code={h['error_code']}")

        else:
            parser.print_help()

    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        client.disconnect()
        print("\n🔌 Disconnected")

if __name__ == "__main__":
    main()
