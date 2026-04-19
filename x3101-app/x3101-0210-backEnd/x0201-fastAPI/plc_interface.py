"""
PLC Interface Module — DB100 & DB200
====================================
Definitions and serialization for the real-time PLC data interface.
DB100: App -> PLC (Commands & Setpoints)
DB200: PLC -> App (Telemetry & Status)
"""

from pydantic import BaseModel, Field
from typing import List, Optional
import struct
from datetime import datetime

# =============================================================================
# DB100: STEP COMMAND (App -> PLC)
# =============================================================================

class DB100StepCommand(BaseModel):
    Watch_Doc: int = 0
    Plan_ID: str = Field("", max_length=20)
    Batch_ID: str = Field("", max_length=20)
    SKU_Name: str = Field("", max_length=30)
    Phase_ID: str = Field("", max_length=10)
    Step_ID: int = 0
    Step_Time_SP: int = 0
    Step_Status: int = 0  # 0=Pending, 1=Active, 2=Complete
    Material_ID: str = Field("", max_length=20)
    Re_Code_ID: str = Field("", max_length=20)
    Req_Qty: float = 0.0
    TT_SP: List[float] = Field(default_factory=lambda: [0.0] * 17) # Array 0..16
    Agitator_Speed: float = 0.0
    High_Shear_SP: float = 0.0
    PH_Target: float = 0.0
    Brix_Target: float = 0.0
    HMI_Command: int = 0 # 0=IDLE, 1=START, 2=PAUSE, 3=ABORT
    Cmd_NewStep: bool = False

    def serialize(self) -> bytes:
        """
        Convert to S7-compatible byte array for DB100.
        Note: Exact offsets depend on TIA Portal alignment.
        This is a conceptual packed representation.
        """
        # Conceptual serialization logic (using standard packing)
        # S7 Strings have a 2-byte header [max_len, act_len]
        def pack_s7_string(s: str, max_len: int) -> bytes:
            s_bytes = s.encode('ascii')[:max_len]
            return struct.pack('BB', max_len, len(s_bytes)) + s_bytes.ljust(max_len, b'\x00')

        payload = b""
        payload += struct.pack('>h', self.Watch_Doc) # Int (2 bytes)
        payload += pack_s7_string(self.Plan_ID, 20)
        payload += pack_s7_string(self.Batch_ID, 20)
        payload += pack_s7_string(self.SKU_Name, 30)
        payload += pack_s7_string(self.Phase_ID, 10)
        payload += struct.pack('>h', self.Step_ID)
        payload += struct.pack('>h', self.Step_Time_SP)
        payload += struct.pack('>h', self.Step_Status)
        payload += pack_s7_string(self.Material_ID, 20)
        payload += pack_s7_string(self.Re_Code_ID, 20)
        payload += struct.pack('>f', self.Req_Qty) # Real (4 bytes)
        
        # TT_SP Array
        for val in self.TT_SP[:17]:
            payload += struct.pack('>f', val)
            
        payload += struct.pack('>f', self.Agitator_Speed)
        payload += struct.pack('>f', self.High_Shear_SP)
        payload += struct.pack('>f', self.PH_Target)
        payload += struct.pack('>f', self.Brix_Target)
        payload += struct.pack('>h', self.HMI_Command)
        payload += struct.pack('?', self.Cmd_NewStep) # Bool
        
        return payload

# =============================================================================
# DB200: TELEMETRY (PLC -> App)
# =============================================================================

class DB200Telemetry(BaseModel):
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
    def from_bytes(cls, data: bytes) -> "DB200Telemetry":
        """Parse S7 byte array from DB200."""
        # Unpack according to structure
        # (Conceptual offsets)
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
