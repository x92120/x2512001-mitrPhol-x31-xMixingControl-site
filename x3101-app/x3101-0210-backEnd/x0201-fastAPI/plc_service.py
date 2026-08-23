"""
PLC Service — Direct S7-1200 Communication via snap7
=====================================================
Manages the TCP connection to the Siemens S7-1200 PLC and provides
high-level functions for reading/writing Data Blocks.

DB1510: Step Command   (App → PLC)  — Single step control
DB1511: Full Recipe    (App → PLC)  — Full recipe array (128 steps)
DB1512: Telemetry      (PLC → App)  — Live sensor data
DB1513: Handshake      (PLC → App)  — Step completion confirmation
"""

import struct
import logging
import os
from typing import Optional, List, Dict, Any
from threading import RLock

logger = logging.getLogger(__name__)

# ─── Configuration ───────────────────────────────────────────────────────────
PLC_IP = os.getenv("PLC_IP", "192.168.21.210")
PLC_RACK = int(os.getenv("PLC_RACK", "0"))
PLC_SLOT = int(os.getenv("PLC_SLOT", "1"))

# Data Block Numbers (Defaults for Plant 1)
DB_STEP_CMD       = 1510
DB_FULL_RECIPE    = 1511
DB_TELEMETRY      = 1512
DB_HANDSHAKE      = 1513
DB_ACTUAL_RECIPE  = 1517

def get_db_number(base_type: str, plant_id: int) -> int:
    """
    Returns the DB number based on the plant ID (1, 2, or 3).
    Plant 1: 151x, Plant 2: 152x, Plant 3: 153x
    """
    offset = 1500 + (int(plant_id) * 10)
    if base_type == 'step_cmd': return offset + 0
    if base_type == 'full_recipe': return offset + 1
    if base_type == "telemetry": return offset + 2
    if base_type == 'handshake': return offset + 3
    if base_type == 'actual': return offset + 7
    return offset


# ─── S7 String Helpers ───────────────────────────────────────────────────────
def pack_s7_string(s: str, max_len: int) -> bytes:
    """Pack a Python string into S7 String format (2-byte header + padded data)."""
    s_bytes = s.encode('ascii', errors='replace')[:max_len]
    return struct.pack('BB', max_len, len(s_bytes)) + s_bytes.ljust(max_len, b'\x00')

def unpack_s7_string(data: bytes, offset: int, max_len: int) -> str:
    """Unpack an S7 String from a byte buffer."""
    actual_len = data[offset + 1]
    return data[offset + 2: offset + 2 + actual_len].decode('ascii', errors='replace').strip('\x00')


# ─── PLC Connection Manager ─────────────────────────────────────────────────
class PLCConnection:
    """Thread-safe snap7 connection manager for S7-1200."""

    def __init__(self, ip: str = PLC_IP, rack: int = PLC_RACK, slot: int = PLC_SLOT):
        self.ip = ip
        self.rack = rack
        self.slot = slot
        self._client = None
        self._lock = RLock()

    @property
    def is_connected(self) -> bool:
        try:
            return self._client is not None and self._client.get_connected()
        except Exception:
            return False

    def connect(self) -> bool:
        """Establish connection to the PLC."""
        with self._lock:
            try:
                import snap7
                if self.is_connected:
                    return True
                self._client = snap7.client.Client()
                self._client.connect(self.ip, self.rack, self.slot)
                logger.info(f"✅ Connected to PLC at {self.ip} (rack={self.rack}, slot={self.slot})")
                return True
            except Exception as e:
                logger.error(f"❌ Failed to connect to PLC at {self.ip}: {e}")
                self._client = None
                return False

    def disconnect(self):
        """Close the PLC connection."""
        with self._lock:
            if self._client:
                try:
                    self._client.disconnect()
                except Exception:
                    pass
                self._client = None
                logger.info("🔌 PLC disconnected")

    def db_read(self, db_number: int, start: int, size: int) -> Optional[bytes]:
        """Read bytes from a Data Block."""
        with self._lock:
            try:
                if not self.is_connected:
                    self.connect()
                if self._client:
                    return bytes(self._client.db_read(db_number, start, size))
            except Exception as e:
                logger.error(f"PLC db_read error (DB{db_number}): {e}")
                self._client = None
        return None

    def db_write(self, db_number: int, start: int, data: bytes) -> bool:
        """Write bytes to a Data Block (supports large chunks)."""
        with self._lock:
            try:
                if not self.is_connected:
                    self.connect()
                if self._client:
                    import snap7
                    ba = bytearray(data)
                    # Write the entire data in one shot if it is small enough, 
                    # or in 240-byte chunks with a small sleep to avoid TCP flooding the S7 CPU
                    import time
                    chunk_size = 100
                    for offset in range(0, len(ba), chunk_size):
                        chunk = ba[offset : offset + chunk_size]
                        self._client.db_write(db_number, start + offset, chunk)
                        time.sleep(0.05) # 50ms delay between chunks to let PLC breathe
                    logger.info(f"✅ PLC db_write OK: DB{db_number}, offset={start}, size={len(data)}")
                    return True
            except Exception as e:
                logger.error(f"❌ PLC db_write error (DB{db_number}): {e}")
                self._client = None
        return False


# ─── Singleton PLC Instance ─────────────────────────────────────────────────
plc = PLCConnection()

# ─── Process PLC Connection (192.168.21.51) ──────────────────────────────────
# Hosts FB0501/502/503 (FB_BATCHING) with sBatchDetail.Material[x].Req
# Used for A1010 (Auto Batching Major) weight targets
PROC_PLC_IP   = os.getenv("PROC_PLC_IP", "192.168.21.51")
PROC_PLC_RACK = int(os.getenv("PROC_PLC_RACK", "0"))
PROC_PLC_SLOT = int(os.getenv("PROC_PLC_SLOT", "1"))

proc_plc = PLCConnection(ip=PROC_PLC_IP, rack=PROC_PLC_RACK, slot=PROC_PLC_SLOT)

# DB0501 layout constants (FB0501_Batching_Mix_02 instance DB)
# sBatchDetail.Material[x].Req = Real (4 bytes)
# Offset formula: 1108 + (material_index_0based * 20)
_BATCHING_DB_BASE    = 500          # DB500=Plant1, DB501=Plant2, DB502=Plant3
_MAT_REQ_BASE_OFFSET = 1120         # Material[1].Req start offset
_MAT_BLOCK_SIZE      = 16           # bytes per Material struct (Req+Tar+Act+Err+pad)
# SCAN interlock bit: DB500.DBX498.0 (Plant1), DB501.DBX498.0 (Plant2), DB502.DBX498.0 (Plant3)
# When SCAN=OFF → write blocked (old system uses SCADA DB0102 values instead)
_SCAN_FLAG_BYTE      = 498          # byte offset within Batching DB
_SCAN_FLAG_BIT       = 0            # bit 0 = LSB (DBX498.0)


def get_batching_db(plant_id: int) -> int:
    """DB500=Plant1, DB501=Plant2, DB502=Plant3"""
    return 499 + int(plant_id)


def check_scan_bit(plant_id: int = 1) -> bool:
    """
    Returns True if Scan bit is ON (new App method active).
    Reads DB500.DBX498.0 / DB501.DBX498.0 / DB502.DBX498.0 (per plant).
    When SCAN=OFF → App must NOT write Material.Req to PLC (old system keeps control).
    """
    db = get_batching_db(plant_id)
    try:
        if not proc_plc.is_connected:
            proc_plc.connect()
        d = proc_plc.db_read(db, _SCAN_FLAG_BYTE, 1)
        if d:
            return bool(d[0] & (1 << _SCAN_FLAG_BIT))  # bit 0 = LSB
    except Exception as e:
        logger.warning(f"[Scan check] Error reading DB{db}.DBX{_SCAN_FLAG_BYTE}.{_SCAN_FLAG_BIT}: {e}")
    return False  # fail-safe: assume OFF (safe)



# ─── Process-PLC Flowmeter Actual Offsets (DB500/DB501/DB503) ────────────────
FLOWMETER_ACT_OFFSETS = {
    1: 2960,  # Material[1] IBC
    2: 3122,  # Material[2] LS in Line
    3: 3284,  # Material[3] MIS
    4: 3446,  # Material[4] RO-Water
}

def get_process_db(plant_id: int) -> int:
    pid = int(plant_id)
    if pid == 1:
        return 500
    elif pid == 2:
        return 501
    else:
        return 503


# ─── Process-PLC Circulation Temperature Offsets (DB2003/DB2004/DB2006) ──────
CIR_TEMP_DB_MAP = {
    1: 2003,  # Line 1: DB2003.DBD0
    2: 2004,  # Line 2: DB2004.DBD0
    3: 2006,  # Line 3: DB2006.DBD0
    4: 2006   # Line 4: DB2006.DBD0
}

def read_circulation_temp(plant_id: int = 1) -> float:
    """
    Read real-time Circulation Temperature (TT CIR) from Process-PLC DB2003/2004/2006.
    Used for Cooling step and transfer temperature tracking.
    """
    db = CIR_TEMP_DB_MAP.get(int(plant_id), 2003)
    try:
        if not proc_plc.is_connected:
            proc_plc.connect()
        raw = proc_plc.db_read(db, 0, 4)
        if raw:
            return round(struct.unpack('>f', raw)[0], 2)
    except Exception as e:
        logger.error(f"[TT CIR] Error reading DB{db}: {e}")
    return 0.0


def read_a1010_material_actuals(plant_id: int = 1) -> Dict[str, float]:
    """
    Read real-time liquid flowmeter actuals from Process-PLC DB500/DB501/DB503.
    Offsets:
      Material[1] (IBC):      Offset 2960 (Float)
      Material[2] (LS):       Offset 3122 (Float)
      Material[3] (MIS):      Offset 3284 (Float)
      Material[4] (RO-Water): Offset 3446 (Float)
    """
    db = get_process_db(plant_id)
    result = {"ibc_act": 0.0, "ls_act": 0.0, "mis_act": 0.0, "ro_act": 0.0}
    try:
        if not proc_plc.is_connected:
            proc_plc.connect()
        raw_ibc = proc_plc.db_read(db, FLOWMETER_ACT_OFFSETS[1], 4)
        if raw_ibc: result["ibc_act"] = round(struct.unpack('>f', raw_ibc)[0], 3)

        raw_ls = proc_plc.db_read(db, FLOWMETER_ACT_OFFSETS[2], 4)
        if raw_ls: result["ls_act"] = round(struct.unpack('>f', raw_ls)[0], 3)

        raw_mis = proc_plc.db_read(db, FLOWMETER_ACT_OFFSETS[3], 4)
        if raw_mis: result["mis_act"] = round(struct.unpack('>f', raw_mis)[0], 3)

        raw_ro = proc_plc.db_read(db, FLOWMETER_ACT_OFFSETS[4], 4)
        if raw_ro: result["ro_act"] = round(struct.unpack('>f', raw_ro)[0], 3)
    except Exception as e:
        logger.error(f"[A1010 Flowmeter] Error reading DB{db}: {e}")
    return result


def write_a1010_material_req(plant_id: int, materials: list) -> bool:
    """
    Write Material[x].Req weights to Process-PLC DB0501/502/503.
    Called before starting A1010 phase (Auto Batching Major).

    Args:
        plant_id: 1, 2, or 3
        materials: list of dicts [{'req': float}, ...] max 4 items; 0.0 = skip slot.
    Returns:
        True if all writes succeeded, False otherwise.

    Note: SCAN interlock — DB5xx.DBX498.0 must be TRUE before write is allowed.
          If SCAN=OFF → returns False immediately, no write occurs (old system keeps control).
    """
    # ── SCAN interlock check ────────────────────────────────────────────────
    if not check_scan_bit(plant_id):
        db = get_batching_db(plant_id)
        logger.warning(
            f"[A1010] BLOCKED — Plant {plant_id} DB{db}.DBX{_SCAN_FLAG_BYTE}.{_SCAN_FLAG_BIT} (SCAN) is OFF. "            f"Operator must enable SCAN on SCADA HMI before auto batching."
        )
        return False

    db = get_batching_db(plant_id)
    ok_all = True

    try:
        if not proc_plc.is_connected:
            proc_plc.connect()

        for i, mat in enumerate(materials[:4]):
            req_val = float(mat.get('req', 0.0) if isinstance(mat, dict) else mat)
            offset = _MAT_REQ_BASE_OFFSET + i * _MAT_BLOCK_SIZE
            data = struct.pack('>f', req_val)
            ok = proc_plc.db_write(db, offset, data)
            logger.info(
                f"[A1010] Plant {plant_id} DB{db}+{offset} Material[{i+1}].Req = {req_val:.3f} kg — {'OK' if ok else 'FAIL'}"
            )
            if not ok:
                ok_all = False

    except Exception as e:
        logger.error(f"[A1010] write_a1010_material_req error: {e}")
        ok_all = False

    return ok_all


# ─── Recipe Step Serialization (78 bytes per step) ──────────────────────────
def serialize_recipe_step(step: Dict[str, Any]) -> bytes:
    """
    Pack a single recipe step into the 78-byte type_RecipeStep structure.
    
    Layout:
      +0   Seq           Int(2)
      +2   Phase_No      Int(2)
      +4   Sub_Step      Int(2)
      +6   Action_Code   String[10](12)
      +18  Phase_ID      String[10](12)
      +30  Re_Code       String[20](22)
      +52  Target_Weight Real(4)
      +56  Temp_SP       Real(4)
      +60  Temp_Low      Real(4)
      +64  Temp_High     Real(4)
      +68  Agitator_SP   Real(4)
      +72  HighShear_SP  Real(4)
      +76  Step_Time     Int(2)
    Total: 78 bytes
    """
    data = b""
    data += struct.pack('>h', int(step.get('seq', 0)))
    data += struct.pack('>h', int(step.get('phase_no', 0)))
    data += struct.pack('>h', int(step.get('sub_step', 0)))
    data += pack_s7_string(str(step.get('action_code', '')), 10)
    data += pack_s7_string(str(step.get('phase_id', '')), 10)
    data += pack_s7_string(str(step.get('re_code', '')), 20)
    data += struct.pack('>f', float(step.get('target_weight', 0.0)))
    data += struct.pack('>f', float(step.get('temp_sp', 0.0)))
    data += struct.pack('>f', float(step.get('temp_low', 0.0)))
    data += struct.pack('>f', float(step.get('temp_high', 0.0)))
    data += struct.pack('>f', float(step.get('agitator_sp', 0.0)))
    data += struct.pack('>f', float(step.get('highshear_sp', 0.0)))
    data += struct.pack('>h', int(step.get('step_time', 0)))
    return data  # 78 bytes


def serialize_empty_step() -> bytes:
    """Pack an empty/unused recipe step (all zeros, 78 bytes)."""
    return b'\x00' * 78


# ─── Full Recipe Serialization (DB1511) ──────────────────────────────────────
def serialize_full_recipe(
    batch_id: str,
    sku_id: str,
    hmi_command: int,
    total_steps: int,
    active_step: int,
    steps: List[Dict[str, Any]]
) -> bytes:
    """
    Pack a full recipe into the DB1511 binary structure.
    
    Header (52 bytes):
      +0   Batch_ID       String[20](22)
      +22  SKU_ID         String[20](22)
      +44  HMI_Command    Int(2)
      +46  Total_Steps    Int(2)
      +48  Active_Step    Int(2)
      +50  Cmd_LoadRecipe Bool(1)
      +51  Padding        Byte(1)
    
    Steps Array (128 × 78 = 9,984 bytes):
      +52  Steps[1]       type_RecipeStep(78)
      +130 Steps[2]       ...
      ...
    
    Total: 10,036 bytes
    """
    MAX_STEPS = 128

    # Header
    header = b""
    header += pack_s7_string(batch_id, 20)        # +0
    header += pack_s7_string(sku_id, 20)           # +22
    header += struct.pack('>h', hmi_command)       # +44
    header += struct.pack('>h', total_steps)       # +46
    header += struct.pack('>h', active_step)       # +48
    header += struct.pack('?', True)               # +50 Cmd_LoadRecipe = TRUE
    header += b'\x00'                              # +51 padding

    # Steps array (only send actual steps + 1 empty step to clear end marker)
    steps_data = b""
    for step in steps:
        steps_data += serialize_recipe_step(step)
    
    # Add one empty step at the end to ensure the PLC sees a clean termination
    steps_data += serialize_empty_step()

    return header + steps_data


# ─── High-Level Functions ────────────────────────────────────────────────────

def write_full_recipe_to_plc(
    batch_id: str,
    sku_id: str,
    steps: List[Dict[str, Any]],
    plant_id: int = 1
) -> bool:
    """
    Assemble the full recipe array and write it to DB15x1 on the PLC.
    Returns True if the write was successful.
    """
    total = len(steps)
    payload = serialize_full_recipe(
        batch_id=batch_id,
        sku_id=sku_id,
        hmi_command=2,   # HOLD — wait for heartbeat pulse (1) from frontend before running
        total_steps=total,
        active_step=1,   # Start at first step
        steps=steps
    )
    db_number = get_db_number('full_recipe', plant_id)
    logger.info(f"📦 Writing full recipe to DB{db_number}: "
                f"batch={batch_id}, sku={sku_id}, steps={total}, size={len(payload)} bytes")
    return plc.db_write(db_number, 0, payload)


def read_handshake(plant_id: int = 1) -> Optional[Dict[str, Any]]:
    """
    Read Handshake DB to detect step completion.
    
    Layout:
      +0  Step_Complete  Bool(1)
      +2  Finished_Step  Int(2)
      +4  End_Temp       Real(4)
      +8  End_Weight     Real(4)
      +12 Error_Flag     Bool(1)
      +14 Error_Code     Int(2)
    """
    db_number = get_db_number('handshake', plant_id)
    data = plc.db_read(db_number, 0, 16)
    if data is None:
        return None
    
    step_complete = bool(data[0] & 0x01)
    finished_step = struct.unpack_from('>h', data, 2)[0]
    end_temp = struct.unpack_from('>f', data, 4)[0]
    end_weight = struct.unpack_from('>f', data, 8)[0]
    error_flag = bool(data[12] & 0x01)
    error_code = struct.unpack_from('>h', data, 14)[0]

    return {
        "step_complete": step_complete,
        "finished_step": finished_step,
        "end_temp": round(end_temp, 2),
        "end_weight": round(end_weight, 2),
        "error_flag": error_flag,
        "error_code": error_code
    }


def read_telemetry(plant_id: int = 1) -> Optional[Dict[str, Any]]:
    """
    Read Telemetry DB for live PLC status.
    """
    db_number = get_db_number('telemetry', plant_id)
    try:
        data = plc.db_read(db_number, 0, 30)  # +2 bytes for PLC_Step_FC at DBW28
    except Exception as e:
        logger.error(f"PLC db_read error (DB{db_number}): {e}")
        return None
    if data is None:
        return None

    watchdog      = struct.unpack_from('>h', data, 0)[0]
    plc_state     = struct.unpack_from('>h', data, 2)[0]
    current_step  = struct.unpack_from('>h', data, 4)[0]
    step_timer    = struct.unpack_from('>h', data, 6)[0]
    mix_temp      = struct.unpack_from('>f', data, 8)[0]
    mix_weight    = struct.unpack_from('>f', data, 12)[0]
    agitator_act  = struct.unpack_from('>f', data, 16)[0]
    highshear_act = struct.unpack_from('>f', data, 20)[0]
    hopper_weight = struct.unpack_from('>f', data, 24)[0]
    # DBW28: FC_MapPhaseToStep_v2 result (0-28, even) — SKU-independent step name
    plc_step_fc   = struct.unpack_from('>h', data, 28)[0] if len(data) >= 30 else 0

    return {
        "watchdog": watchdog,
        "Watch_Doc": watchdog,
        "plc_state": plc_state,
        "PLC_State": plc_state,
        "current_step": current_step,
        "Current_Step": current_step,
        "step_timer": step_timer,
        "Step_Timer": step_timer,
        "mix_temp": round(mix_temp, 2),
        "MixTank_Temp": round(mix_temp, 2),
        "mix_weight": round(mix_weight, 2),
        "MixTank_Weight": round(mix_weight, 2),
        "agitator_act": round(agitator_act, 2),
        "Agitator_Act": round(agitator_act, 2),
        "highshear_act": round(highshear_act, 2),
        "HighShear_Act": round(highshear_act, 2),
        "hopper_weight": round(hopper_weight, 2),
        "Hopper_Weight": round(hopper_weight, 2),
        "plc_step_fc": int(plc_step_fc),
        "PLC_Step_FC": int(plc_step_fc),
        "liquid_ibc_act": round(struct.unpack('>f', proc_plc.db_read(get_process_db(plant_id), 2960, 4))[0], 3) if proc_plc.is_connected else 0.0,
        "liquid_ls_act": round(struct.unpack('>f', proc_plc.db_read(get_process_db(plant_id), 3122, 4))[0], 3) if proc_plc.is_connected else 0.0,
        "liquid_mis_act": round(struct.unpack('>f', proc_plc.db_read(get_process_db(plant_id), 3284, 4))[0], 3) if proc_plc.is_connected else 0.0,
        "liquid_ro_act": round(struct.unpack('>f', proc_plc.db_read(get_process_db(plant_id), 3446, 4))[0], 3) if proc_plc.is_connected else 0.0,
        "circulation_temp": read_circulation_temp(plant_id),
        "Circulation_Temperature": read_circulation_temp(plant_id),
    }

# ─── Recipe Deserialization ─────────────────────────────────────────────────
def deserialize_recipe_step(data: bytes, offset: int) -> Dict[str, Any]:
    return {
        'seq': struct.unpack_from('>h', data, offset + 0)[0],
        'phase_no': struct.unpack_from('>h', data, offset + 2)[0],
        'sub_step': struct.unpack_from('>h', data, offset + 4)[0],
        'action_code': unpack_s7_string(data, offset + 6, 10),
        'phase_id': unpack_s7_string(data, offset + 18, 10),
        're_code': unpack_s7_string(data, offset + 30, 20),
        'target_weight': round(struct.unpack_from('>f', data, offset + 52)[0], 2),
        'temp_sp': round(struct.unpack_from('>f', data, offset + 56)[0], 2),
        'temp_low': round(struct.unpack_from('>f', data, offset + 60)[0], 2),
        'temp_high': round(struct.unpack_from('>f', data, offset + 64)[0], 2),
        'agitator_sp': round(struct.unpack_from('>f', data, offset + 68)[0], 2),
        'highshear_sp': round(struct.unpack_from('>f', data, offset + 72)[0], 2),
        'step_time': struct.unpack_from('>h', data, offset + 76)[0]
    }

def read_recipe_from_plc(db_number: int) -> Optional[Dict[str, Any]]:
    """Read dynamic length recipe from PLC to reconstruct UI table."""
    header = plc.db_read(db_number, 0, 52)
    if not header: return None
    
    total_steps = struct.unpack_from(">h", header, 46)[0]
    active_step = struct.unpack_from(">h", header, 48)[0]
    
    steps = []
    if 0 < total_steps <= 128:
        # Read only the used steps to prevent memory lag
        steps_data = plc.db_read(db_number, 52, total_steps * 78)
        if steps_data:
            for i in range(total_steps):
                steps.append(deserialize_recipe_step(steps_data, i * 78))
                
    return {
        "batch_id": unpack_s7_string(header, 0, 20),
        "sku_id": unpack_s7_string(header, 22, 20),
        "total_steps": total_steps,
        "active_step": active_step,
        "steps": steps
    }

def decode_dtl(data: bytes, offset: int) -> Optional[str]:
    """Decode 12-byte Siemens DTL into ISO 8601 string."""
    try:
        y, m, d, wd, hr, mn, sc, ns = struct.unpack_from('>HBBBBBBL', data, offset)
        if y == 0: return None
        return f"{y:04d}-{m:02d}-{d:02d}T{hr:02d}:{mn:02d}:{sc:02d}"
    except Exception:
        return None

def read_full_actuals(plant_id: int = 1) -> Optional[Dict[str, Any]]:
    """Read DB1517/1527/1537 Full Actual Results Array."""
    db_number = get_db_number('actual', plant_id)
    # Header 50 bytes + 128*60 bytes = 7730 bytes
    data = plc.db_read(db_number, 0, 7730)
    if data is None:
        return None
        
    batch_id = unpack_s7_string(data, 0, 20)
    sku_id = unpack_s7_string(data, 22, 20)
    total_steps = struct.unpack_from('>h', data, 44)[0]
    current_seq = struct.unpack_from('>h', data, 46)[0]
    batch_status = struct.unpack_from('>h', data, 48)[0]
    
    steps = []
    base_offset = 50
    step_size = 60
    
    # Read up to the maximum we need
    limit = max(total_steps, current_seq)
    if limit <= 0 or limit > 128:
        limit = 128
        
    for i in range(limit):
        off = base_offset + (i * step_size)
        step_idx, ph_num, sub_step = struct.unpack_from('>hhh', data, off)
        
        if step_idx == 0:
            continue
            
        r_weight, r_temp, r_agit, r_shear, r_brix, r_ph = struct.unpack_from('>ffffff', data, off + 6)
        time_start = decode_dtl(data, off + 30)
        time_end = decode_dtl(data, off + 42)
        duration = struct.unpack_from('>l', data, off + 54)[0]
        status_code = struct.unpack_from('>h', data, off + 58)[0]
        
        steps.append({
            "step_index": step_idx,
            "phase_number": ph_num,
            "sub_step": sub_step,
            "actual_weight": round(r_weight, 2),
            "actual_temp": round(r_temp, 2),
            "actual_agitator": round(r_agit, 2),
            "actual_highshear": round(r_shear, 2),
            "actual_brix": round(r_brix, 2),
            "actual_ph": round(r_ph, 2),
            "time_start": time_start,
            "time_end": time_end,
            "duration_sec": duration,
            "status_code": status_code
        })
        
    # Derive current phase_id and step_id from the active step entry (current_seq matches step_index)
    current_phase_id = None
    current_step_id = None
    if current_seq > 0:
        for s in steps:
            if s["step_index"] == current_seq:
                current_phase_id = f"p{str(s['phase_number']).zfill(4)}"
                current_step_id = s["sub_step"]
                break

    return {
        "batch_id": batch_id,
        "sku_id": sku_id,
        "total_steps": total_steps,
        "current_seq": current_seq,
        "batch_status": batch_status,
        "phase_id": current_phase_id,   # e.g. "p010" — used by frontend on page refresh
        "step_id": current_step_id,     # e.g. 10 — used by frontend on page refresh
        "steps": steps
    }


def clear_actuals_in_plc(plant_id: int = 1) -> bool:
    """
    Zero-out DB15x7 (Actual Results) to clear all PLC execution history.
    Header (50 bytes) + 128 steps × 60 bytes = 7,730 bytes total → write all zeros.
    """
    db_number = get_db_number('actual', plant_id)
    zeros = b'\x00' * 7730
    logger.info(f"🗑️  Clearing actual results in DB{db_number} ({len(zeros)} bytes)...")
    result = plc.db_write(db_number, 0, zeros)
    if result:
        logger.info(f"✅ DB{db_number} (Actuals) cleared successfully")
    else:
        logger.error(f"❌ Failed to clear DB{db_number} (Actuals)")
    return result


def clear_plc_step_cmd(plant_id: int = 1) -> bool:
    """
    Write HMI_Command=9 (RESET) + Step_No=0 + Batch_ID="" to DB15x0.
    Called after batch Done to signal PLC to return to IDLE state.
    """
    db_number = get_db_number("step_cmd", plant_id)   # DB1510/1520/1530
    try:
        # Build 94-byte payload: all zeros except HMI_Command=9 (RESET) at +22
        payload = bytearray(94)
        # +0  Batch_ID String[20](22 bytes) — fill with S7 string header + empty
        payload[0] = 20   # max_len
        payload[1] = 0    # actual_len = 0 (empty string)
        # +22 HMI_Command = 9 (RESET)
        struct.pack_into(">h", payload, 22, 9)
        # +24 Step_No = 0 (already 0)
        # +26 Phase_ID empty, +38 Re_Code empty, rest zeros
        result = plc.db_write(db_number, 0, bytes(payload))
        if result:
            logger.info(f"✅ [ClearCmd] DB{db_number} Plant{plant_id} reset to IDLE (HMI_Command=9, Step_No=0)")
        else:
            logger.warning(f"[ClearCmd] DB{db_number} write failed")
        return result
    except Exception as e:
        logger.error(f"[ClearCmd] DB{db_number} error: {e}")
        return False

def set_step_complete_in_plc(plant_id: int) -> bool:
    """
    Sets DB15x3 Offset 0.0 (Step_complete) to True.
    Triggered by App for manual steps (Scan/QC).
    """
    db_number = get_db_number('handshake', plant_id)
    try:
        data = plc.db_read(db_number, 0, 1)
        if data is None:
            return False
        import snap7.util
        byte_data = bytearray(data)
        snap7.util.set_bool(byte_data, 0, 0, True)
        result = plc.db_write(db_number, 0, bytes(byte_data))
        if result:
            logger.info(f"✅ [Handshake] Set Step_complete (DB{db_number} +0.0) to TRUE for Plant {plant_id}")
        return result
    except Exception as e:
        logger.error(f"Failed to set Step_complete for Plant {plant_id}: {e}")
        return False
