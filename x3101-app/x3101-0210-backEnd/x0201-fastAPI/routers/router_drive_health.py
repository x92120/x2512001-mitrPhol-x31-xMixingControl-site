"""
Drive Health Router — G120C PROFINET Health Monitor
=====================================================
Reads G120C drive health data from PLC DB100 via S7 GET (python-snap7).

Architecture:
  G120C × 7 ──PROFINET──▶ PLC 192.168.21.51 (Drive PLC)
                                  │ RDREC → DB100 (280 bytes)
                                  │
  FastAPI ──S7 GET──────────────▶┘

NOTE: Uses DRIVE_PLC (192.168.21.51) NOT the Mixing PLC (192.168.21.210).
      RDREC must run on the PLC that owns the G120C IO devices.

Drive Index → IP mapping:
  0 = Motor MIX1       (192.168.21.141)
  1 = Motor MIX2       (192.168.21.142)
  2 = Circulation MIX1 (192.168.21.143)
  3 = Circulation MIX2 (192.168.21.144)
  4 = Motor MIX3       (192.168.21.146)
  5 = Circulation MIX3 (192.168.21.147)
  6 = Cooling MIX3     (192.168.21.148)
"""

import struct
import logging
import os
import sqlite3
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/drive-health", tags=["Drive Health"])

# ─── Drive PLC Connection (192.168.21.51) ────────────────────────────────────
# Separate from the Mixing PLC (192.168.21.210) — different IO System
DRIVE_PLC_IP   = os.getenv("DRIVE_PLC_IP",   "192.168.21.51")
DRIVE_PLC_RACK = int(os.getenv("DRIVE_PLC_RACK", "0"))
DRIVE_PLC_SLOT = int(os.getenv("DRIVE_PLC_SLOT", "1"))

from plc_service import PLCConnection
_drive_plc = PLCConnection(
    ip=DRIVE_PLC_IP,
    rack=DRIVE_PLC_RACK,
    slot=DRIVE_PLC_SLOT
)

# ─── Drive Definitions ───────────────────────────────────────────────────────
DRIVES = [
    {"id": 0, "name": "Motor MIX1",       "ip": "192.168.21.141", "type": "Motor",       "mix": 1},
    {"id": 1, "name": "Motor MIX2",       "ip": "192.168.21.142", "type": "Motor",       "mix": 2},
    {"id": 2, "name": "Circulation MIX1", "ip": "192.168.21.143", "type": "Circulation", "mix": 1},
    {"id": 3, "name": "Circulation MIX2", "ip": "192.168.21.144", "type": "Circulation", "mix": 2},
    {"id": 4, "name": "Motor MIX3",       "ip": "192.168.21.146", "type": "Motor",       "mix": 3},
    {"id": 5, "name": "Circulation MIX3", "ip": "192.168.21.147", "type": "Circulation", "mix": 3},
    {"id": 6, "name": "Cooling MIX3",     "ip": "192.168.21.148", "type": "Cooling",     "mix": 3},
]

# ─── DB100 Memory Map ────────────────────────────────────────────────────────
# UDT_DriveHealth = 40 bytes per drive (aligned)
# +0  ZSW1        WORD   (2 bytes)  — Status Word 1 from Telegram 1
# +2  HIW         WORD   (2 bytes)  — Actual Speed (0-16384 = 0-100%)
# +4  Current_Pct REAL   (4 bytes)  — r0027 Output current %
# +8  Temperature REAL   (4 bytes)  — r0035 Motor temperature °C
# +12 DC_Voltage  REAL   (4 bytes)  — r0070 DC Link Voltage V
# +16 Op_Hours    DINT   (4 bytes)  — r0042 Operating hours
# +20 Fault_Code  WORD   (2 bytes)  — r0945[0] Active fault code
# +22 Status2     WORD   (2 bytes)  — r0052 Extended status
# +24 Speed_RPM   REAL   (4 bytes)  — r0021 Actual speed RPM
# +28 Ready       BOOL   (1 byte)   — ZSW1.bit0
# +29 Running     BOOL   (1 byte)   — ZSW1.bit2
# +30 Fault       BOOL   (1 byte)   — ZSW1.bit3
# +31 Alarm       BOOL   (1 byte)   — ZSW1.bit7
# +32 RDREC_Busy  BOOL   (1 byte)
# +33 RDREC_Error BOOL   (1 byte)
# +34 Padding     WORD   (2 bytes)
# +36 RDREC_Status DWORD (4 bytes)
# Total = 40 bytes

DB_HEALTH   = 150  # เปลี่ยนจาก 100 → ชนกับ DB เดิมบน PLC .51
STRIDE      = 56   # bytes per drive
TOTAL_BYTES = STRIDE * len(DRIVES)  # 392 bytes

# ─── G120C Fault Code Database (from SINAMICS G120C List Manual) ─────────────
# Source: Siemens SINAMICS G120C Operating Instructions / List Manual
# Format: code → { desc, remedy, severity }
FAULT_DB: Dict[int, Dict[str, str]] = {
    # ── System / Internal ──────────────────────────────────────────────────
    0:     {"desc": "No Fault",                                    "remedy": "-",                                                                  "sev": "ok"},
    1:     {"desc": "F00001 - Computer system error",              "remedy": "Power cycle the drive. If persistent, contact Siemens service.",      "sev": "critical"},
    11:    {"desc": "F00011 - Main contactor faulty",              "remedy": "Check main contactor wiring and control circuit. Verify p0210.",      "sev": "critical"},
    12:    {"desc": "F00012 - DC link: Charging time exceeded",    "remedy": "Check pre-charge circuit / charging resistor. Check p0210 (input voltage).", "sev": "warning"},
    30:    {"desc": "F00030 - Hardware fault",                     "remedy": "Power cycle. If persistent, replace control unit or power module.",   "sev": "critical"},
    52:    {"desc": "F00052 - Power stack failure",                "remedy": "Check power connections. Power cycle. Replace power module if needed.","sev": "critical"},
    56:    {"desc": "F00056 - Overcurrent",                        "remedy": "Check motor for short circuit/ground fault. Increase ramp time p1120. Check motor parameters.", "sev": "critical"},
    60:    {"desc": "F00060 - DC link: Undervoltage",              "remedy": "Check input voltage ≥ min spec. Check main contactor and fuses. Verify p0210.", "sev": "critical"},
    62:    {"desc": "F00062 - DC link: Overvoltage",               "remedy": "Check for regenerative load. Extend decel ramp p1121. Add braking resistor if needed.", "sev": "critical"},
    67:    {"desc": "F00067 - Setpoint/actual position deviation",  "remedy": "Check mechanical load. Check encoder signal. Verify position controller gains.", "sev": "warning"},
    72:    {"desc": "F00072 - Power section: Overtemperature",     "remedy": "Check cooling fan. Clean heatsink fins. Reduce load or duty cycle. Check ambient temp.", "sev": "critical"},
    92:    {"desc": "F00092 - Motor overtemperature (I²t model)",  "remedy": "Reduce motor load. Improve cooling. Verify p0626 motor thermal time constant.", "sev": "warning"},
    103:   {"desc": "F00103 - Internal voltage fault",             "remedy": "Power cycle the drive. Check input supply stability. If persistent, replace drive.", "sev": "critical"},
    205:   {"desc": "F00205 - Drive monitoring: Overcurrent",      "remedy": "Check motor cable for short circuit. Check motor winding insulation. Verify rated current p0305.", "sev": "critical"},

    # ── Drive Control (F07xxx) ─────────────────────────────────────────────
    7010:  {"desc": "F07010 - Motor: Setpoint/actual speed deviation","remedy": "Check mechanical load for jam/blockage. Verify speed limits p1080/p1082. Check drive sizing.", "sev": "critical"},
    7011:  {"desc": "F07011 - Motor: Stall protection (closed-loop)", "remedy": "Check motor for overload or jam. Verify motor data (p0304–p0311). Reduce load.", "sev": "critical"},
    7012:  {"desc": "F07012 - Motor stall",                        "remedy": "Check mechanical jam. Verify rated current p0305. Increase stall detection time p0607.", "sev": "critical"},
    7080:  {"desc": "F07080 - Speed controller output at limit",   "remedy": "Check motor sizing vs load. Check torque limit p1520/p1521. Verify motor data.", "sev": "warning"},
    7086:  {"desc": "F07086 - Speed actual value outside tolerance","remedy": "Check encoder/speed feedback. Verify p2163 (tolerance band). Check load coupling.", "sev": "warning"},
    7091:  {"desc": "F07091 - Motor speed not plausible",          "remedy": "Check encoder connection. Verify motor wiring phase sequence. Check p1300.", "sev": "warning"},

    # ── Motor Temperature ──────────────────────────────────────────────────
    7010:  {"desc": "F07010 - Motor overtemperature",              "remedy": "Reduce load. Improve ventilation. Check ambient temperature ≤ 40°C. Check sensor wiring.", "sev": "critical"},
    7016:  {"desc": "F07016 - Motor: PTC/KTY fault",               "remedy": "Check PTC/KTY temperature sensor wiring and connections. Verify p0601/p0604.", "sev": "warning"},

    # ── Power Unit (F30xxx) ────────────────────────────────────────────────
    30001: {"desc": "F30001 - Power unit: Overcurrent",            "remedy": "Check motor cables for short circuit/ground fault. Increase ramp time p1120. Verify motor parameters p0304–p0311.", "sev": "critical"},
    30002: {"desc": "F30002 - DC link: Overvoltage",               "remedy": "Extend deceleration ramp p1121. Check for regenerative braking. Consider braking resistor.", "sev": "critical"},
    30003: {"desc": "F30003 - DC link: Undervoltage",              "remedy": "Check mains voltage ≥ rated. Check input fuses and main contactor. Verify p0210.", "sev": "critical"},
    30004: {"desc": "F30004 - Power unit: Overtemperature (heatsink)","remedy": "Check internal cooling fan. Clean heatsink. Reduce ambient temp. Reduce load/duty cycle. Verify p0290.", "sev": "critical"},
    30005: {"desc": "F30005 - Power unit: I²t overload",           "remedy": "Reduce load. Reduce switching frequency p1800. Check duty cycle. Allow drive to cool.", "sev": "warning"},
    30011: {"desc": "F30011 - Line phase failure",                  "remedy": "Check all 3 input phases for correct voltage. Check input fuses and connections.", "sev": "critical"},
    30017: {"desc": "F30017 - Input voltage failure",               "remedy": "Check mains supply. Verify input voltage is within drive rating. Check upstream protection.", "sev": "critical"},
    30021: {"desc": "F30021 - Ground fault",                        "remedy": "Check motor cables for insulation damage. Check motor winding for ground fault. Measure insulation resistance.", "sev": "critical"},
    30022: {"desc": "F30022 - Motor phase failure",                  "remedy": "Check motor cable connections U, V, W. Check motor terminal box. Verify contactor contacts.", "sev": "critical"},

    # ── PROFINET / Communication (F08xxx) ──────────────────────────────────
    8501:  {"desc": "F08501 - PROFINET: Telegram failure",         "remedy": "Check PROFINET cable connections. Verify PLC program is sending cyclic data. Check network switch.", "sev": "critical"},
    8500:  {"desc": "F08500 - PROFINET: Configuration fault",      "remedy": "Verify drive configuration matches TIA Portal device config. Re-download hardware config.", "sev": "critical"},
}


def describe_fault(code: int) -> Dict[str, str]:
    """Return fault info dict with desc, remedy, severity."""
    if code == 0:
        return {"desc": "No Fault", "remedy": "-", "sev": "ok"}
    entry = FAULT_DB.get(code)
    if entry:
        return entry
    return {
        "desc":   f"F{code:05d} - Fault Active",
        "remedy": f"Check r0949 fault value on drive HMI for detail. Refer to SINAMICS G120C List Manual.",
        "sev":    "warning"
    }


def decode_zsw1(zsw1: int) -> Dict[str, bool]:
    """Decode ZSW1 Status Word 1 bits (PROFIdrive standard)."""
    return {
        "ready_to_switch_on": bool(zsw1 & (1 << 0)),   # bit 0
        "ready":              bool(zsw1 & (1 << 1)),   # bit 1
        "running":            bool(zsw1 & (1 << 2)),   # bit 2
        "fault":              bool(zsw1 & (1 << 3)),   # bit 3
        "coast_stop":         bool(zsw1 & (1 << 4)),   # bit 4 (0=active)
        "quick_stop":         bool(zsw1 & (1 << 5)),   # bit 5 (0=active)
        "switch_on_inhibit":  bool(zsw1 & (1 << 6)),   # bit 6
        "alarm":              bool(zsw1 & (1 << 7)),   # bit 7
        "setpoint_reached":   bool(zsw1 & (1 << 10)),  # bit 10
        "operation_enabled":  bool(zsw1 & (1 << 11)),  # bit 11
    }


def compute_health_score(drive_data: Dict[str, Any]) -> int:
    """
    Compute a 0-100 health score based on drive parameters.
    Rules:
      - Fault active      → 0
      - Temp > 80°C       → -30
      - Temp > 60°C       → -15
      - Current > 90%     → -20
      - Current > 75%     → -10
      - RDREC Error       → -10
      - Alarm active      → -5
    """
    if drive_data.get("fault"):
        return 0

    score = 100

    temp = drive_data.get("temperature", 0)
    if temp > 80:
        score -= 30
    elif temp > 60:
        score -= 15

    current = drive_data.get("current_a", 0)  # in Amps
    if current > 20:    # >20A = overload warning
        score -= 20
    elif current > 15:  # >15A = high load
        score -= 10

    if drive_data.get("rdrec_error"):
        score -= 10

    if drive_data.get("alarm"):
        score -= 5

    return max(0, score)


def parse_drive_bytes(data: bytes, drive_idx: int, drive_info: Dict) -> Dict[str, Any]:
    """Parse 40-byte drive record from DB100."""
    base = drive_idx * STRIDE

    zsw1         = struct.unpack_from('>H', data, base + 0)[0]
    hiw          = struct.unpack_from('>H', data, base + 2)[0]
    current_pct  = struct.unpack_from('>f', data, base + 4)[0]
    temperature  = struct.unpack_from('>f', data, base + 8)[0]
    dc_voltage   = struct.unpack_from('>f', data, base + 12)[0]
    op_hours     = struct.unpack_from('>i', data, base + 16)[0]
    fault_code   = struct.unpack_from('>H', data, base + 20)[0]
    fault_info   = describe_fault(fault_code)
    status2      = struct.unpack_from('>H', data, base + 22)[0]
    speed_rpm    = struct.unpack_from('>f', data, base + 24)[0]
    # StatusFlags WORD at +28: bit0=Ready, bit2=Running, bit3=Fault, bit7=Alarm, bit8=Busy, bit9=Error
    status_flags = struct.unpack_from('>H', data, base + 28)[0]
    # +30 _Pad (WORD), +32 RDREC_Status (DWORD), +36 _Pad2 (DWORD)
    
    # Expanded Telemetry (v2 UDT: 56 bytes)
    try:
        output_v   = struct.unpack_from('>f', data, base + 40)[0]
        torque_pct = struct.unpack_from('>f', data, base + 44)[0]
        power_kw   = struct.unpack_from('>f', data, base + 48)[0]
        energy_kwh = struct.unpack_from('>f', data, base + 52)[0]
    except struct.error:
        output_v = torque_pct = power_kw = energy_kwh = 0.0

    ready        = bool(status_flags & (1 << 0))
    running      = bool(status_flags & (1 << 2))
    fault        = bool(status_flags & (1 << 3))
    alarm        = bool(status_flags & (1 << 7))
    rdrec_busy   = bool(status_flags & (1 << 8))
    rdrec_error  = bool(status_flags & (1 << 9))

    # Clamp NaN/Inf from uninitialized REAL fields
    def safe_float(v: float) -> float:
        import math
        return 0.0 if (math.isnan(v) or math.isinf(v)) else round(v, 1)

    speed_pct = round((hiw / 16384) * 100, 1) if hiw > 0 else 0.0

    drive_data = {
        "id":            drive_info["id"],
        "name":          drive_info["name"],
        "ip":            drive_info["ip"],
        "type":          drive_info["type"],
        "mix":           drive_info["mix"],
        # Telegram 1 data
        "zsw1_hex":      f"0x{zsw1:04X}",
        "zsw1_bits":     decode_zsw1(zsw1),
        "speed_pct":     speed_pct,
        # RDREC Acyclic data
        "current_a":     safe_float(current_pct),   # r0027 in Amperes (field renamed)
        "current_pct":   safe_float(current_pct),   # keep for compatibility
        "temperature":   safe_float(temperature),
        "dc_voltage":    safe_float(dc_voltage),
        "output_v":      safe_float(output_v),
        "torque_pct":    safe_float(torque_pct),
        "power_kw":      safe_float(power_kw),
        "energy_kwh":    safe_float(energy_kwh),
        "op_hours":      max(0, op_hours),
        # r0945 keeps old code after clear — only show if ZSW1.bit3 (fault) is truly active
        "fault_code":    fault_code if fault else 0,
        "fault_desc":    fault_info["desc"]   if fault else "No Fault",
        "fault_remedy":  fault_info["remedy"] if fault else "-",
        "fault_sev":     fault_info["sev"]    if fault else "ok",
        "speed_rpm":     safe_float(speed_rpm),
        "status2_hex":   f"0x{status2:04X}",
        # Status flags
        "ready":         ready,
        "running":       running,
        "fault":         fault,
        "alarm":         alarm,
        # RDREC state
        "rdrec_busy":    rdrec_busy,
        "rdrec_error":   rdrec_error,
        # data_valid = True if we have ANY real value (not just error-flag based)
        "data_valid":    temperature != 0.0 or current_pct != 0.0 or dc_voltage != 0.0 or running,
    }

    drive_data["health"] = compute_health_score(drive_data)
    drive_data["status"] = (
        "FAULT"   if fault   else
        "ALARM"   if alarm   else
        "RUNNING" if running else
        "READY"   if ready   else
        "OFFLINE"
    )

    return drive_data


# ─── SQLite Fault Event Persistence (30-day) ─────────────────────────────────
_DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "fault_events.db")
os.makedirs(os.path.dirname(_DB_PATH), exist_ok=True)


def _init_fault_db():
    """Create fault_events table if not exists."""
    with sqlite3.connect(_DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS fault_events (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                drive_id    INTEGER NOT NULL,
                drive_name  TEXT,
                ts          TEXT NOT NULL,
                event       TEXT,
                fault_code  INTEGER,
                fault_desc  TEXT,
                fault_remedy TEXT,
                fault_sev   TEXT,
                temperature REAL,
                current_pct REAL,
                status      TEXT
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_drive_ts ON fault_events(drive_id, ts)")
        conn.commit()


def _persist_fault_event(drive_idx: int, drive_name: str, event: str, data: Dict):
    """Write a fault transition event to SQLite."""
    try:
        with sqlite3.connect(_DB_PATH) as conn:
            conn.execute("""
                INSERT INTO fault_events
                (drive_id,drive_name,ts,event,fault_code,fault_desc,fault_remedy,fault_sev,temperature,current_pct,status)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)
            """, (
                drive_idx,
                drive_name,
                datetime.now().isoformat(),
                event,
                data.get("fault_code", 0),
                data.get("fault_desc", ""),
                data.get("fault_remedy", ""),
                data.get("fault_sev", "ok"),
                data.get("temperature", 0),
                data.get("current_pct", 0),
                data.get("status", ""),
            ))
            # Purge events older than 30 days
            cutoff = (datetime.now() - timedelta(days=30)).isoformat()
            conn.execute("DELETE FROM fault_events WHERE ts < ?", (cutoff,))
            conn.commit()
    except Exception as e:
        logger.warning(f"fault_events DB write error: {e}")


_init_fault_db()

# ─── In-memory history (30-min rolling) ──────────────────────────────────────
_history: Dict[int, List[Dict]] = {i: [] for i in range(len(DRIVES))}
_last_fault_code: Dict[int, int] = {i: -1 for i in range(len(DRIVES))}  # track transitions
MAX_HISTORY = 360  # 30min @ 5s polling


def _append_history(drive_idx: int, data: Dict):
    """Append current reading to history ring buffer + persist fault events."""
    fault_code = data.get("fault_code", 0)
    _history[drive_idx].append({
        "ts":           datetime.now().isoformat(),
        "current_pct":  data.get("current_pct", 0),
        "temperature":  data.get("temperature", 0),
        "speed_pct":    data.get("speed_pct", 0),
        "health":       data.get("health", 0),
        "fault_code":   fault_code,
        "fault_desc":   data.get("fault_desc", ""),
        "fault_remedy": data.get("fault_remedy", ""),
        "fault_sev":    data.get("fault_sev", "ok"),
        "status":       data.get("status", "OFFLINE"),
    })
    if len(_history[drive_idx]) > MAX_HISTORY:
        _history[drive_idx].pop(0)

    # Persist fault transition events to SQLite
    prev = _last_fault_code[drive_idx]
    if fault_code != prev and prev != -1:  # skip very first reading
        drive_name = DRIVES[drive_idx]["name"] if drive_idx < len(DRIVES) else f"Drive{drive_idx}"
        event = "FAULT_CLEARED" if fault_code == 0 else "FAULT_ACTIVE"
        _persist_fault_event(drive_idx, drive_name, event, data)
    _last_fault_code[drive_idx] = fault_code


# ─── Core Read Function ───────────────────────────────────────────────────────
def read_all_drives() -> Optional[List[Dict[str, Any]]]:
    """Read DB100 from Drive PLC (192.168.21.51) and parse all 7 drives."""
    try:
        data = _drive_plc.db_read(DB_HEALTH, 0, TOTAL_BYTES)
        if data is None:
            logger.warning(f"DB{DB_HEALTH} read from {DRIVE_PLC_IP} returned None — PLC may be offline or DB100 not created yet")
            return None

        results = []
        for i, drive_info in enumerate(DRIVES):
            parsed = parse_drive_bytes(data, i, drive_info)
            _append_history(i, parsed)
            results.append(parsed)

        return results

    except Exception as e:
        logger.error(f"read_all_drives error ({DRIVE_PLC_IP}): {e}")
        return None


# ─── API Endpoints ────────────────────────────────────────────────────────────

@router.get("/all")
def get_all_drive_health():
    """
    Read all 7 G120C drives from PLC DB100.
    Returns live health data including current, temperature, DC voltage, fault codes.
    """
    drives = read_all_drives()

    if drives is None:
        # Return offline template so dashboard shows something
        return {
            "ok": False,
            "plc_ip": DRIVE_PLC_IP,
            "db": DB_HEALTH,
            "timestamp": datetime.now().isoformat(),
            "message": f"Drive PLC ({DRIVE_PLC_IP}) DB{DB_HEALTH} unavailable — check connection or DB100 not created yet in TIA Portal",
            "drives": [
                {
                    "id": d["id"], "name": d["name"], "ip": d["ip"],
                    "type": d["type"], "mix": d["mix"],
                    "status": "OFFLINE", "health": 0,
                    "running": False, "fault": False, "ready": False, "alarm": False,
                    "current_pct": 0, "temperature": 0, "dc_voltage": 0,
                    "op_hours": 0, "fault_code": 0, "fault_desc": "No Data",
                    "speed_pct": 0, "speed_rpm": 0, "data_valid": False,
                    "rdrec_error": True, "rdrec_busy": False,
                }
                for d in DRIVES
            ],
        }

    # Summary stats
    running_count  = sum(1 for d in drives if d["running"])
    fault_count    = sum(1 for d in drives if d["fault"])
    alarm_count    = sum(1 for d in drives if d["alarm"])
    avg_health     = round(sum(d["health"] for d in drives) / len(drives))
    avg_temp       = round(sum(d["temperature"] for d in drives) / len(drives), 1)
    avg_current    = round(sum(d["current_pct"] for d in drives) / len(drives), 1)

    return {
        "ok":           True,
        "plc_ip":       DRIVE_PLC_IP,
        "db":           DB_HEALTH,
        "timestamp":    datetime.now().isoformat(),
        "summary": {
            "total":      len(drives),
            "running":    running_count,
            "fault":      fault_count,
            "alarm":      alarm_count,
            "avg_health": avg_health,
            "avg_temp":   avg_temp,
            "avg_current": avg_current,
        },
        "drives": drives,
    }


@router.get("/drive/{drive_id}")
def get_single_drive(drive_id: int):
    """Read a single drive by index (0-6)."""
    if drive_id < 0 or drive_id >= len(DRIVES):
        raise HTTPException(status_code=400, detail=f"drive_id must be 0-{len(DRIVES)-1}")

    drives = read_all_drives()
    if drives is None:
        raise HTTPException(status_code=503, detail="PLC DB100 unavailable")

    return drives[drive_id]


@router.get("/history/{drive_id}")
def get_drive_history(drive_id: int, points: int = 60):
    """
    Get rolling history for a specific drive (last N points, max 360).
    Used for trend charts in the dashboard.
    """
    if drive_id < 0 or drive_id >= len(DRIVES):
        raise HTTPException(status_code=400, detail=f"drive_id must be 0-{len(DRIVES)-1}")

    points = min(points, MAX_HISTORY)
    hist = _history[drive_id][-points:]

    return {
        "drive_id":   drive_id,
        "drive_name": DRIVES[drive_id]["name"],
        "points":     len(hist),
        "history":    hist,
    }


@router.get("/fault-log")
def get_fault_log():
    """
    Return current active faults from all drives.
    """
    drives = read_all_drives()
    faults = []

    if drives:
        for d in drives:
            if d.get("fault") or d.get("fault_code", 0) != 0:
                faults.append({
                    "drive_id":   d["id"],
                    "drive_name": d["name"],
                    "fault_code": d["fault_code"],
                    "fault_desc": d["fault_desc"],
                    "temperature":d["temperature"],
                    "current_pct":d["current_pct"],
                    "time":       datetime.now().strftime("%H:%M:%S"),
                    "severity":   "Critical" if d["fault"] else "Warning",
                })

    return {
        "ok":        True,
        "timestamp": datetime.now().isoformat(),
        "faults":    faults,
        "count":     len(faults),
    }


@router.get("/fault-history/{drive_id}")
def get_fault_history(drive_id: int, days: int = 30, limit: int = 200):
    """
    Return persisted fault event history for a specific drive.
    Queries SQLite — survives backend restarts, retains up to 30 days.
    """
    if drive_id < 0 or drive_id >= len(DRIVES):
        raise HTTPException(status_code=400, detail=f"drive_id must be 0-{len(DRIVES)-1}")

    cutoff = (datetime.now() - timedelta(days=days)).isoformat()

    try:
        with sqlite3.connect(_DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("""
                SELECT * FROM fault_events
                WHERE drive_id = ? AND ts >= ?
                ORDER BY ts DESC
                LIMIT ?
            """, (drive_id, cutoff, limit)).fetchall()
    except Exception as e:
        logger.warning(f"fault_events DB read error: {e}")
        rows = []

    events = [dict(r) for r in rows]

    return {
        "drive_id":   drive_id,
        "drive_name": DRIVES[drive_id]["name"],
        "days":       days,
        "events":     events,
        "count":      len(events),
    }
