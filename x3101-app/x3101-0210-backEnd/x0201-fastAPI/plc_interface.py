"""
PLC Interface Module — DB1510, DB1511, DB1512, DB1513
======================================================
Pydantic models and serialization for the real-time PLC data interface.

DB1510: App -> PLC (Single Step Commands & Setpoints)
DB1511: App -> PLC (Full Recipe Array — 128 steps)
DB1512: PLC -> App (Telemetry & Status)
DB1513: PLC -> App (Handshake / Step Completion)
"""

from pydantic import BaseModel, Field
from typing import List, Optional
import struct
from datetime import datetime

# =============================================================================
# S7 String Helpers
# =============================================================================

def pack_s7_string(s: str, max_len: int) -> bytes:
    """Pack a Python string into S7 String format (2-byte header + padded data)."""
    s_bytes = s.encode('ascii', errors='replace')[:max_len]
    return struct.pack('BB', max_len, len(s_bytes)) + s_bytes.ljust(max_len, b'\x00')


# =============================================================================
# DB1510: STEP COMMAND (App -> PLC) — Single Step
# =============================================================================

class DB1510StepCommand(BaseModel):
    """
    DB1510: Step Command (App → PLC)
    Matches the 88-byte type_StepCommand on PLC at 192.168.21.210.
    
    Byte Map (88 bytes):
      +0    Batch_ID       String[20](22)
      +22   HMI_Command    Int(2)
      +24   Step_No        Int(2)
      +26   Phase_ID       String[10](12)
      +38   Re_Code        String[20](22)
      +60   Target_Weight  Real(4)
      +64   Temp_SP        Real(4)
      +68   Temp_Low       Real(4)
      +72   Temp_High      Real(4)
      +76   Agitator_SP    Real(4)
      +80   HighShear_SP   Real(4)
      +84   Step_Time      Int(2)
      +86   Cmd_NewStep    Bool(1)
      +87   Padding        Byte(1)
    """
    Batch_ID: str = Field("", max_length=20)
    HMI_Command: int = 0         # 0=IDLE, 1=START, 2=PAUSE, 3=ABORT, 9=RESET
    Step_No: int = 0
    Phase_ID: str = Field("", max_length=10)
    Re_Code: str = Field("", max_length=20)
    Target_Weight: float = 0.0
    Temp_SP: float = 0.0
    Temp_Low: float = 0.0
    Temp_High: float = 0.0
    Agitator_SP: float = 0.0
    HighShear_SP: float = 0.0
    Step_Time: int = 0            # Seconds
    Cmd_NewStep: bool = False

    def serialize(self) -> bytes:
        """
        Convert to S7-compatible byte array for DB1510.
        Matches TIA Portal type_StepCommand layout exactly.
        Total: 88 bytes.
        """
        payload = b""
        payload += pack_s7_string(self.Batch_ID, 20)       # +0   String[20](22)
        payload += struct.pack('>h', self.HMI_Command)     # +22  Int(2)
        payload += struct.pack('>h', self.Step_No)         # +24  Int(2)
        payload += pack_s7_string(self.Phase_ID, 10)       # +26  String[10](12)
        payload += pack_s7_string(self.Re_Code, 20)        # +38  String[20](22)
        payload += struct.pack('>f', self.Target_Weight)   # +60  Real(4)
        payload += struct.pack('>f', self.Temp_SP)         # +64  Real(4)
        payload += struct.pack('>f', self.Temp_Low)        # +68  Real(4)
        payload += struct.pack('>f', self.Temp_High)       # +72  Real(4)
        payload += struct.pack('>f', self.Agitator_SP)     # +76  Real(4)
        payload += struct.pack('>f', self.HighShear_SP)    # +80  Real(4)
        payload += struct.pack('>h', self.Step_Time)       # +84  Int(2)
        payload += struct.pack('?', self.Cmd_NewStep)      # +86  Bool(1)
        payload += b'\x00'                                 # +87  Padding(1)
        
        return payload  # 88 bytes


# =============================================================================
# DB1511: FULL RECIPE ARRAY (App -> PLC) — 128 steps
# =============================================================================

class DB1511RecipeStep(BaseModel):
    """A single step in the full recipe array (78 bytes packed)."""
    Seq: int = 0                  # Flat sequence number (1-128)
    Phase_No: int = 0             # Phase number (10, 20, 30...)
    Sub_Step: int = 0             # Step within phase (10, 20, 30...)
    Action_Code: str = Field("", max_length=10)
    Phase_ID: str = Field("", max_length=10)
    Re_Code: str = Field("", max_length=20)
    Target_Weight: float = 0.0
    Temp_SP: float = 0.0
    Temp_Low: float = 0.0
    Temp_High: float = 0.0
    Agitator_SP: float = 0.0
    HighShear_SP: float = 0.0
    Step_Time: int = 0            # Seconds

    def serialize(self) -> bytes:
        """Pack this step into a 78-byte binary representation."""
        data = b""
        data += struct.pack('>h', self.Seq)
        data += struct.pack('>h', self.Phase_No)
        data += struct.pack('>h', self.Sub_Step)
        data += pack_s7_string(self.Action_Code, 10)
        data += pack_s7_string(self.Phase_ID, 10)
        data += pack_s7_string(self.Re_Code, 20)
        data += struct.pack('>f', self.Target_Weight)
        data += struct.pack('>f', self.Temp_SP)
        data += struct.pack('>f', self.Temp_Low)
        data += struct.pack('>f', self.Temp_High)
        data += struct.pack('>f', self.Agitator_SP)
        data += struct.pack('>f', self.HighShear_SP)
        data += struct.pack('>h', self.Step_Time)
        return data  # 78 bytes


class DB1511FullRecipe(BaseModel):
    """Full recipe with header and 128-step array (10,036 bytes packed)."""
    Batch_ID: str = Field("", max_length=20)
    SKU_ID: str = Field("", max_length=20)
    HMI_Command: int = 0     # 0=IDLE, 1=START, 2=PAUSE, 3=ABORT, 9=RESET
    Total_Steps: int = 0     # How many steps are populated (1-128)
    Active_Step: int = 1     # Pointer to current step (1-128)
    Cmd_LoadRecipe: bool = True
    Steps: List[DB1511RecipeStep] = Field(default_factory=list)

    def serialize(self) -> bytes:
        """Pack the full recipe into DB1511 binary format (10,036 bytes)."""
        MAX_STEPS = 128

        # Header (52 bytes)
        header = b""
        header += pack_s7_string(self.Batch_ID, 20)       # +0
        header += pack_s7_string(self.SKU_ID, 20)          # +22
        header += struct.pack('>h', self.HMI_Command)      # +44
        header += struct.pack('>h', self.Total_Steps)       # +46
        header += struct.pack('>h', self.Active_Step)       # +48
        header += struct.pack('?', self.Cmd_LoadRecipe)     # +50
        header += b'\x00'                                   # +51 padding

        # Steps (128 × 78 = 9,984 bytes)
        steps_data = b""
        for i in range(MAX_STEPS):
            if i < len(self.Steps):
                steps_data += self.Steps[i].serialize()
            else:
                steps_data += b'\x00' * 78  # Empty step

        return header + steps_data  # Total: 10,036 bytes


# =============================================================================
# DB1512: TELEMETRY (PLC -> App)
# =============================================================================

class DB1512Telemetry(BaseModel):
    Watchdog: int = 0
    PLC_State: int = 0 # 0=Ready, 1=Run, 2=Hold, 9=Error
    Current_Step: int = 0
    Step_Timer: int = 0
    Step_Status_Act: int = 0 # 0=Init, 1=Dosing, 2=Mixing
    MixTank_Temp: float = 0.0
    MixTank_Weight: float = 0.0
    Agitator_Act: float = 0.0
    HighShear_Act: float = 0.0
    PH_Actual: float = 0.0
    Brix_Actual: float = 0.0
    Hopper_Weight: float = 0.0
    Last_Update: datetime = Field(default_factory=datetime.now)

    @classmethod
    def from_bytes(cls, data: bytes) -> "DB1512Telemetry":
        """Parse S7 byte array from DB1512."""
        watchdog, p_state, curr_step, s_timer, s_status_act = struct.unpack_from('>hhhhh', data, 0)
        temp, weight, ag_act, hs_act, ph, brix, hopper = struct.unpack_from('>fffffff', data, 10)
        
        return cls(
            Watchdog=watchdog,
            PLC_State=p_state,
            Current_Step=curr_step,
            Step_Timer=s_timer,
            Step_Status_Act=s_status_act,
            MixTank_Temp=temp,
            MixTank_Weight=weight,
            Agitator_Act=ag_act,
            HighShear_Act=hs_act,
            PH_Actual=ph,
            Brix_Actual=brix,
            Hopper_Weight=hopper
        )


# =============================================================================
# DB1513: HANDSHAKE (PLC -> App)
# =============================================================================

class DB1513Handshake(BaseModel):
    Step_Complete: bool = False
    Finished_Step: int = 0
    End_Temp: float = 0.0
    End_Weight: float = 0.0
    Error_Flag: bool = False
    Error_Code: int = 0

    @classmethod
    def from_bytes(cls, data: bytes) -> "DB1513Handshake":
        """Parse S7 byte array from DB1513."""
        step_complete = bool(data[0] & 0x01)
        finished_step = struct.unpack_from('>h', data, 2)[0]
        end_temp = struct.unpack_from('>f', data, 4)[0]
        end_weight = struct.unpack_from('>f', data, 8)[0]
        error_flag = bool(data[12] & 0x01)
        error_code = struct.unpack_from('>h', data, 14)[0]

        return cls(
            Step_Complete=step_complete,
            Finished_Step=finished_step,
            End_Temp=end_temp,
            End_Weight=end_weight,
            Error_Flag=error_flag,
            Error_Code=error_code
        )
