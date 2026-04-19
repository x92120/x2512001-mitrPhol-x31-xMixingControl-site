"""
PLC Datablock Serializer — DB 1780
===================================
Serializes SKU recipe data into a structured format matching
the Siemens S7-1200 datablock layout.

DB 1780 Structure:
  Header: PlanID, BatchID, SkuID, SkuName, PlantID, BatchSize, ProcessCount
  32 × UDT_Process:
    ProcessNo(Int), PhaseID(Int), StepCount, ProcessActive
    8 × UDT_ProcessStep:
      StepNo, ActionCode, ReCode, Destination, Require, LowTol, HighTol,
      Temperature, TempLow, TempHigh, AgitatorRPM, HighShearRPM,
      StepTime, StepTimerCtl, SetupStep, Condition, QC flags, BrixSP, PhSP
"""

from typing import List, Dict, Any, Optional
import re
import logging

logger = logging.getLogger(__name__)

MAX_PROCESSES = 32
MAX_STEPS_PER_PROCESS = 8


def _parse_int(val: Any, default: int = 0) -> int:
    """Safely parse a value to int."""
    if val is None:
        return default
    try:
        # Handle strings like "p0010" → 10, "A1010" → 1010, "1010" → 1010
        s = str(val).strip()
        # Strip leading letters (e.g. "p0010" → "0010", "A1010" → "1010")
        s = re.sub(r'^[a-zA-Z]+', '', s)
        return int(s) if s else default
    except (ValueError, TypeError):
        return default


def _parse_float(val: Any, default: float = 0.0) -> float:
    """Safely parse a value to float."""
    if val is None:
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def _empty_step() -> Dict[str, Any]:
    """Return an empty UDT_ProcessStep with all defaults."""
    return {
        "StepNo": 0,
        "ActionCode": "",
        "ReCode": "",
        "Destination": 0,
        "Require": 0.0,
        "LowTol": 0.0,
        "HighTol": 0.0,
        "Temperature": 0.0,
        "TempLow": 0.0,
        "TempHigh": 0.0,
        "AgitatorRPM": 0.0,
        "HighShearRPM": 0.0,
        "StepTime": 0,
        "StepTimerCtl": 0,
        "SetupStep": 0,
        "Condition": 0,
        "QcTemp": False,
        "RecordSteam": False,
        "RecordCTW": False,
        "BrixRecord": False,
        "PhRecord": False,
        "MasterStep": False,
        "StepActive": False,
        "BrixSP": 0.0,
        "PhSP": 0.0,
    }


def _empty_process(index: int) -> Dict[str, Any]:
    """Return an empty UDT_Process with all defaults."""
    return {
        "ProcessNo": index * 10,  # P0010, P0020, etc.
        "PhaseID": 0,
        "StepCount": 0,
        "ProcessActive": False,
        "Steps": [_empty_step() for _ in range(MAX_STEPS_PER_PROCESS)],
    }


def _sku_step_to_udt(step: Dict[str, Any]) -> Dict[str, Any]:
    """Convert a single SKU step record to UDT_ProcessStep format."""
    return {
        "StepNo": _parse_int(step.get("sub_step"), 0),
        "ActionCode": str(step.get("action_code") or step.get("action") or "")[:20],
        "ReCode": str(step.get("re_code") or "")[:20],
        "Destination": _parse_int(step.get("destination"), 0),
        "Require": _parse_float(step.get("require"), 0.0),
        "LowTol": _parse_float(step.get("low_tol"), 0.0),
        "HighTol": _parse_float(step.get("high_tol"), 0.0),
        "Temperature": _parse_float(step.get("temperature"), 0.0),
        "TempLow": _parse_float(step.get("temp_low"), 0.0),
        "TempHigh": _parse_float(step.get("temp_high"), 0.0),
        "AgitatorRPM": _parse_float(step.get("agitator_rpm"), 0.0),
        "HighShearRPM": _parse_float(step.get("high_shear_rpm"), 0.0),
        "StepTime": _parse_int(step.get("step_time"), 0),
        "StepTimerCtl": _parse_int(step.get("step_timer_control"), 0),
        "SetupStep": _parse_int(step.get("setup_step"), 0),
        "Condition": _parse_int(step.get("step_condition"), 0),
        "QcTemp": bool(step.get("qc_temp")),
        "RecordSteam": bool(step.get("record_steam_pressure")),
        "RecordCTW": bool(step.get("record_ctw")),
        "BrixRecord": bool(step.get("operation_brix_record")),
        "PhRecord": bool(step.get("operation_ph_record")),
        "MasterStep": bool(step.get("master_step")),
        "StepActive": True,
        "BrixSP": _parse_float(step.get("brix_sp"), 0.0),
        "PhSP": _parse_float(step.get("ph_sp"), 0.0),
    }


def build_recipe_payload(
    plan_id: str,
    batch_id: str,
    sku_id: str,
    sku_name: str,
    plant_id: str,
    batch_size: float,
    sku_steps: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Build a complete DB 1780 recipe payload from SKU steps.

    Groups steps by phase_number into processes, maps them into
    32 process slots × 8 step slots each.

    Returns a dict matching the DB 1780 structure.
    """

    # --- Group SKU steps by phase_number ---
    phase_groups: Dict[str, List[Dict[str, Any]]] = {}
    for step in sku_steps:
        pn = str(step.get("phase_number") or "0")
        if pn not in phase_groups:
            phase_groups[pn] = []
        phase_groups[pn].append(step)

    # Sort phases by numeric value
    sorted_phases = sorted(
        phase_groups.items(),
        key=lambda x: _parse_int(x[0], 9999)
    )

    # --- Build 32 process slots ---
    processes = []
    for i in range(MAX_PROCESSES):
        if i < len(sorted_phases):
            phase_key, steps = sorted_phases[i]
            # Sort steps by sub_step
            steps.sort(key=lambda s: _parse_int(s.get("sub_step"), 0))

            # Truncate to MAX_STEPS_PER_PROCESS
            active_steps = steps[:MAX_STEPS_PER_PROCESS]

            # Build UDT steps (pad to 8)
            udt_steps = []
            for s in active_steps:
                udt_steps.append(_sku_step_to_udt(s))
            while len(udt_steps) < MAX_STEPS_PER_PROCESS:
                udt_steps.append(_empty_step())

            phase_id_raw = active_steps[0].get("phase_id") if active_steps else ""

            processes.append({
                "ProcessNo": _parse_int(phase_key, (i + 1) * 10),
                "PhaseID": _parse_int(phase_id_raw, 0),
                "StepCount": len(active_steps),
                "ProcessActive": True,
                "Steps": udt_steps,
            })
        else:
            processes.append(_empty_process(i + 1))

    # --- Build final DB 1780 payload ---
    return {
        "DB": 1780,
        "DBName": "DB_RecipeData",
        "Header": {
            "PlanID": str(plan_id)[:30],
            "BatchID": str(batch_id)[:30],
            "SkuID": str(sku_id)[:30],
            "SkuName": str(sku_name)[:50],
            "PlantID": _parse_int(plant_id, 1),
            "BatchSize": _parse_float(batch_size, 0.0),
            "ProcessCount": len(sorted_phases),
            "RecipeReady": False,
            "StartCmd": False,
        },
        "Processes": processes,
    }
