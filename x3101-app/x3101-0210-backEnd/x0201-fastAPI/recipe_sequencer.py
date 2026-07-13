"""
recipe_sequencer.py — xMixing Recipe Pre-processor
====================================================
Mirrors FC_MapPhaseToStep SCL logic on the App side.

PURPOSE:
  ไม่ใช้ plc_step_no จาก DB ตรงๆ (ผกผันตามอารมณ์คนกรอก)
  แต่ CALCULATE PLC step จาก phase_type_code + action_code แทน
  แล้วเรียง Group ตาม PLC sequence ที่ตายตัว

PLC SEQUENCE (Fixed):
  0→2→4→6→[8→10 auto]→[Batch OK]→12→14→16→18→20→22→24→26→28→0

CONVERGENCE RULES:
  Step 14 = Fill Minor (GATE) — PLC checks RECIPE_z=14 before allowing Fill Done.
            Auto-inserted for any SKU with A1020 (step 6) even if no DB phases at step 14.
            Includes: x1010(20050/20020) + A1020 preblend transfer + A1010 manual during heating.
  Step 18 = Timed Hold = x1010(step_time>0) + D1010/D1030 all converge here
"""

from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

# ─── PLC Step Sequence (Fixed) ────────────────────────────────────────────────
PLC_STEP_SEQUENCE = [0, 2, 4, 6, 8, 10, 12, 14, 16, 18, 20, 22, 24, 26, 28]

# Steps that auto-advance (no real interlock needed)
PLC_AUTO_STEPS = {8, 10}

# Gate steps: always inserted in execution plan when triggered by specific phase types
# Step 14 = Fill Minor gate: required whenever SKU has A1020 (high shear) phases
# PLC checks RECIPE_z=14 before allowing operator Fill Done to advance
PLC_GATE_STEPS = {
    14: {2},   # step 14 gate inserted when SKU has phase_type_code=2 (A1020)
}

# phase_type_code → label
PHASE_TYPE_LABELS = {
    1: "A1010",  # Auto Batching Major
    2: "A1020",  # High Shear / Pre-blend
    3: "D1010",  # Dissolve Tank 1
    4: "D1030",  # Dissolve Tank 2
    5: "x1010",  # Heating
    6: "x1020",  # Pasteurizer
    7: "x1030",  # Holding / Cooling
    8: "x1040",  # Transfer
}


# ─── Core: FC_MapPhaseToStep equivalent (Python) ─────────────────────────────
def map_phase_to_plc_step(
    phase_type_code: int,
    action_code: int,
    temp_sp: float = 0.0,
    step_time: int = 0,
) -> int:
    """
    Mirror of FC_MapPhaseToStep v2 SCL logic.
    Returns PLC step number (0–28) from phase attributes.

    Used by the pre-processor so App never depends on DB plc_step_no.
    """
    ac = int(action_code or 0)
    ts = float(temp_sp or 0.0)
    st = int(step_time or 0)

    if phase_type_code == 1:   # A1010 — Auto Batching Major
        if ac in (10010, 10020, 10030, 10040):
            return 2   # Auto pipe batching
        elif ac in (30010, 20040):
            return 4   # Manual add / pour
        return 2

    elif phase_type_code == 2:  # A1020 — High Shear
        return 6

    elif phase_type_code == 3:  # D1010 — Dissolve Tank 1
        # All D1010 operations map to PLC step 8 (sequence placeholder).
        # PLC auto-advances through step 8. No step 9 in PLC sequence.
        return 8

    elif phase_type_code == 4:  # D1030 — Dissolve Tank 2
        return 10

    elif phase_type_code == 5:  # x1010 — Heating
        if ac in (20050, 20020):
            return 14  # Fill Minor (Brix water, rinse during heat)
        elif ac in (30500, 30010):
            if st > 0:
                return 18   # Timed Hold
            elif ts >= 83.0:
                return 16   # Second Heat
            else:
                return 12   # Pre-Heat
        return 12

    elif phase_type_code == 6:  # x1020 — Pasteurizer
        return 20

    elif phase_type_code == 7:  # x1030 — Holding / Cooling
        # step 24 (Transfer) uses specific transfer action codes only
        if ac in (30600, 30020):
            return 24   # Transfer to Circulation
        # Everything else (30500 hold, 30010 QC wait) → step 22 QC Hold/Cooling
        return 22

    elif phase_type_code == 8:  # x1040 — Transfer
        return 26

    return 0  # Stand By / Unknown


# ─── Validate: Compare DB plc_step_no vs calculated step ─────────────────────
def validate_step(step: Dict[str, Any]) -> Dict[str, Any]:
    """
    Compare DB plc_step_no vs calculated value.
    Returns dict with 'ok', 'db_step', 'calc_step', 'warning'.
    """
    db_step = int(step.get("plc_step_no") or 0)
    calc_step = map_phase_to_plc_step(
        phase_type_code=int(step.get("phase_type_code") or 0),
        action_code=int(step.get("action_code") or 0),
        temp_sp=float(step.get("temperature") or 0.0),
        step_time=int(step.get("step_time") or 0),
    )
    ok = (db_step == calc_step)
    return {
        "phase_number": step.get("phase_number"),
        "phase_id": step.get("phase_id"),
        "re_code": step.get("re_code"),
        "action_code": step.get("action_code"),
        "db_step": db_step,
        "calc_step": calc_step,
        "ok": ok,
        "warning": None if ok else (
            f"plc_step_no={db_step} in DB but should be {calc_step} "
            f"(phase_type={PHASE_TYPE_LABELS.get(int(step.get('phase_type_code') or 0), '?')},"
            f" action={step.get('action_code')})"
        ),
    }


# ─── Main: Build Execution Sequence ──────────────────────────────────────────
def build_execution_sequence(sku_steps: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Takes raw sku_steps from DB.
    Returns a PLC-ordered execution plan grouped by PLC step.

    Steps are always in PLC sequence order (2→4→6→8→...→28)
    regardless of phase_number ordering in DB.

    Each group contains:
      - plc_step: int
      - auto_pass: bool (step 8, 10)
      - recipe_z: int  (= plc_step, sent as DB1510.z for interlock sync)
      - phases: List[dict]  (all recipe sub-steps for this PLC step)
      - temp_sp: float  (temperature setpoint for this step group)
      - step_time: int  (timer seconds for this step group)
    """
    # 1. Classify each DB step using calculated PLC step (ignore DB plc_step_no)
    classified = []
    warnings = []

    for s in sku_steps:
        ptc = int(s.get("phase_type_code") or 0)
        ac  = int(s.get("action_code") or 0)
        ts  = float(s.get("temperature") or 0.0)
        st  = int(s.get("step_time") or 0)

        calc_step = map_phase_to_plc_step(ptc, ac, ts, st)
        db_step   = int(s.get("plc_step_no") or 0)

        if db_step != calc_step and db_step != 0:
            warnings.append({
                "phase": s.get("phase_number"),
                "re_code": s.get("re_code"),
                "db_step": db_step,
                "calc_step": calc_step,
                "msg": f"DB says {db_step}, should be {calc_step}",
            })

        classified.append({**s, "_plc_step": calc_step})

    # 2. Group by calculated PLC step
    groups: Dict[int, List[dict]] = {}
    for s in classified:
        ps = s["_plc_step"]
        groups.setdefault(ps, []).append(s)

    # 2b. Determine gate steps to auto-insert
    phase_types_used = {int(s.get("phase_type_code") or 0) for s in sku_steps}
    auto_gate_steps = set()
    for gate_step, trigger_types in PLC_GATE_STEPS.items():
        if trigger_types & phase_types_used and gate_step not in groups:
            auto_gate_steps.add(gate_step)
            logger.info(
                f"[Sequencer] Auto-inserting gate step {gate_step} "
                f"(triggered by phase_types {trigger_types & phase_types_used})"
            )

    # 3. Build ordered execution plan
    execution_plan = []
    used_steps = set(groups.keys()) | auto_gate_steps

    for plc_step in PLC_STEP_SEQUENCE:
        if plc_step == 0:
            continue  # Skip stand-by
        if plc_step not in used_steps and plc_step not in PLC_AUTO_STEPS:
            continue  # Skip steps not in this recipe

        phases = groups.get(plc_step, [])
        is_gate = plc_step in auto_gate_steps

        # Determine aggregated temp_sp and step_time for this step group
        # (use max temp_sp and max step_time among all phases)
        temps  = [float(p.get("temperature") or 0.0) for p in phases if p.get("temperature")]
        times  = [int(p.get("step_time") or 0)       for p in phases if p.get("step_time")]

        group = {
            "plc_step":   plc_step,
            "auto_pass":  plc_step in PLC_AUTO_STEPS,
            "gate_step":  is_gate,    # True = auto-inserted, no recipe phases
            "recipe_z":   plc_step,   # ← Sent as DB1510.z for interlock RECIPE_z sync
            "temp_sp":    max(temps) if temps else 0.0,
            "step_time":  max(times) if times else 0,
            "phase_label": PHASE_TYPE_LABELS.get(
                int(phases[0].get("phase_type_code") or 0), "?"
            ) if phases else ("GATE" if is_gate else "AUTO"),
            "phases": sorted(
                phases,
                key=lambda p: (int(p.get("sub_step") or 0), str(p.get("phase_number") or ""))
            ),
        }
        execution_plan.append(group)

    logger.info(
        f"[Sequencer] Built {len(execution_plan)} step groups. "
        f"Warnings: {len(warnings)}"
    )
    if warnings:
        for w in warnings:
            logger.warning(f"[Sequencer] Step mismatch: {w}")

    return {
        "execution_plan": execution_plan,
        "total_plc_steps": len(execution_plan),
        "warnings": warnings,
        "warning_count": len(warnings),
    }


# ─── Helper: Get step command payload for DB1510 write ───────────────────────
def get_step_cmd_payload(
    group: Dict[str, Any],
    batch_id: str,
    phase: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Build DB1510StepCommand fields for a given execution group.

    CRITICAL: Sets z = plc_step (= recipe_z) so the PLC interlock
    RECIPE_z check (DB1520.DBW92 == plc_step) passes correctly.
    """
    p = phase or (group["phases"][0] if group["phases"] else {})

    return {
        "Batch_ID":      batch_id,
        "HMI_Command":   0,
        "Step_No":       group["plc_step"],
        "Phase_ID":      str(p.get("phase_id") or ""),
        "Re_Code":       str(p.get("re_code") or ""),
        "Target_Weight": float(p.get("require") or 0.0),
        "Temp_SP":       float(group["temp_sp"]),
        "Temp_Low":      float(p.get("temp_low") or 0.0),
        "Temp_High":     float(p.get("temp_high") or 0.0),
        "Agitator_SP":   float(p.get("agitator_rpm") or 0.0),
        "HighShear_SP":  float(p.get("high_shear_rpm") or 0.0),
        "Step_Time":     int(group["step_time"]),
        "Cmd_NewStep":   False,
        "Action_Code":   int(p.get("action_code") or 0),
        # z field (DB1510 offset +92) = RECIPE_z for PLC interlock sync
        # PLC checks: DB1520.DBW92 == plc_step to verify App alignment
        "z":             group["recipe_z"],
    }
