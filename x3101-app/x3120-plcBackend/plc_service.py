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
from threading import Lock

logger = logging.getLogger(__name__)

# ─── Configuration ───────────────────────────────────────────────────────────
PLC_IP = os.getenv("PLC_IP", "192.168.21.210")
PLC_RACK = int(os.getenv("PLC_RACK", "0"))
PLC_SLOT = int(os.getenv("PLC_SLOT", "1"))

# Data Block Numbers
DB_STEP_CMD     = 1510
DB_FULL_RECIPE  = 1511
DB_TELEMETRY    = 1512
DB_HANDSHAKE    = 1513

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
        self._lock = Lock()

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
        """Write bytes to a Data Block."""
        with self._lock:
            try:
                if not self.is_connected:
                    self.connect()
                if self._client:
                    import snap7
                    ba = bytearray(data)
                    self._client.db_write(db_number, start, ba)
                    logger.info(f"✅ PLC db_write OK: DB{db_number}, offset={start}, size={len(data)}")
                    return True
            except Exception as e:
                logger.error(f"❌ PLC db_write error (DB{db_number}): {e}")
                self._client = None
        return False


# ─── Singleton PLC Instance ─────────────────────────────────────────────────
plc = PLCConnection()


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

    # Steps array
    steps_data = b""
    for i in range(MAX_STEPS):
        if i < len(steps):
            steps_data += serialize_recipe_step(steps[i])
        else:
            steps_data += serialize_empty_step()

    return header + steps_data


# ─── High-Level Functions ────────────────────────────────────────────────────

def write_full_recipe_to_plc(
    batch_id: str,
    sku_id: str,
    steps: List[Dict[str, Any]]
) -> bool:
    """
    Assemble the full recipe array and write it to DB1511 on the PLC.
    Returns True if the write was successful.
    """
    total = len(steps)
    payload = serialize_full_recipe(
        batch_id=batch_id,
        sku_id=sku_id,
        hmi_command=1,   # START
        total_steps=total,
        active_step=1,   # Start at first step
        steps=steps
    )
    logger.info(f"📦 Writing full recipe to DB{DB_FULL_RECIPE}: "
                f"batch={batch_id}, sku={sku_id}, steps={total}, size={len(payload)} bytes")
    return plc.db_write(DB_FULL_RECIPE, 0, payload)


def read_handshake() -> Optional[Dict[str, Any]]:
    """
    Read DB1513 (Handshake) to detect step completion.
    
    Layout:
      +0  Step_Complete  Bool(1)
      +2  Finished_Step  Int(2)
      +4  End_Temp       Real(4)
      +8  End_Weight     Real(4)
      +12 Error_Flag     Bool(1)
      +14 Error_Code     Int(2)
    """
    data = plc.db_read(DB_HANDSHAKE, 0, 16)
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


def read_telemetry() -> Optional[Dict[str, Any]]:
    """
    Read DB1512 (Telemetry) for live PLC status.
    """
    data = plc.db_read(DB_TELEMETRY, 0, 38)
    if data is None:
        return None

    watchdog = struct.unpack_from('>h', data, 0)[0]
    plc_state = struct.unpack_from('>h', data, 2)[0]
    current_step = struct.unpack_from('>h', data, 4)[0]
    step_timer = struct.unpack_from('>h', data, 6)[0]
    mix_temp = struct.unpack_from('>f', data, 8)[0]
    mix_weight = struct.unpack_from('>f', data, 12)[0]
    agitator_act = struct.unpack_from('>f', data, 16)[0]
    highshear_act = struct.unpack_from('>f', data, 20)[0]
    hopper_weight = struct.unpack_from('>f', data, 24)[0]

    return {
        "watchdog": watchdog,
        "plc_state": plc_state,
        "current_step": current_step,
        "step_timer": step_timer,
        "mix_temp": round(mix_temp, 2),
        "mix_weight": round(mix_weight, 2),
        "agitator_act": round(agitator_act, 2),
        "highshear_act": round(highshear_act, 2),
        "hopper_weight": round(hopper_weight, 2)
    }
