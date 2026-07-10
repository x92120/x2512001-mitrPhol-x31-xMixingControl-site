"""
migrate_add_plc_step.py
========================
เพิ่ม column `plc_step_no` และ `phase_type_code` ใน sku_steps
- plc_step_no    : Int  (Step No reference เดิม)
- phase_type_code: Int  (1-8) → ส่งเป็น DB15x0.RECIPE.Phase_Type ไป PLC
                         PLC CASE ใช้ค่านี้ determine interlock

Phase_Type encoding:
  1 = A1010  Batching Auto
  2 = A1020  High Shear
  3 = D1010  Preblending / Dissolve
  4 = D1030  First Confirm / Secondary Dissolve
  5 = x1010  Pre Heat / Fill Minor / Second Heat / Fill Third
  6 = x1020  Pasteurizer
  7 = x1030  Waiting QC / QC Confirm / Ready Transfer
  8 = x1040  Transferring
  0 = Unknown

Run:
  python3 migrate_add_plc_step.py [--dry-run] [--validate]
"""

import argparse
from database import SessionLocal
from sqlalchemy import text

# ─────────────────────────────────────────────────────────────────────────────
# PHASE_TYPE_CODE — ส่งตรงไป DB15x0.RECIPE.Phase_Type (Byte)
# ─────────────────────────────────────────────────────────────────────────────
PHASE_TYPE_MAP = {
    'A1010': 1,
    'A1020': 2,
    'D1010': 3,
    'D1030': 4,
    'x1010': 5,
    'x1020': 6,
    'x1030': 7,
    'x1040': 8,
}

PHASE_PLC_MAP = {
    'A1010': 2,
    'A1020': 6,
    'D1010': 8,
    'D1030': 10,
    'x1020': 20,
    'x1040': 26,
}

X1010_ACTION_MAP = {
    '30500': 12,
    '30010': 12,
    '20050': 14,
    '20020': 14,
    '20040': 14,
}

X1030_ACTION_MAP = {
    '30010': 21,
    '30500': 22,
    '30600': 24,
    '30020': 24,
}

DEFAULT_STEP = 0


def resolve_plc_step(phase_id, action_code, step_time, temperature, sub_step):
    if not phase_id:
        return DEFAULT_STEP
    pid = phase_id.strip()
    ac  = (action_code or '').strip()
    if pid in PHASE_PLC_MAP:
        return PHASE_PLC_MAP[pid]
    if pid == 'x1010':
        if ac in ('20050', '20020', '20040'):
            return 14
        if ac == '30500' and step_time and step_time > 0 and sub_step >= 30:
            return 18
        if ac in ('30500', '30010') and temperature and temperature >= 83:
            return 16
        return 12
    if pid == 'x1030':
        return X1030_ACTION_MAP.get(ac, 21)
    return DEFAULT_STEP


def run_migration(dry_run=False):
    db = SessionLocal()
    try:
        # Add plc_step_no
        c1 = db.execute(text(
            "SELECT COUNT(*) FROM information_schema.columns "
            "WHERE table_schema=DATABASE() AND table_name='sku_steps' AND column_name='plc_step_no'"
        )).scalar()
        if c1 == 0:
            if not dry_run:
                db.execute(text(
                    "ALTER TABLE sku_steps ADD COLUMN plc_step_no SMALLINT NOT NULL DEFAULT 0 "
                    "COMMENT 'PLC Step No reference'"
                ))
                db.commit()
                print("✅ Column plc_step_no added")
            else:
                print("[DRY] Would add column plc_step_no")
        else:
            print("ℹ️  Column plc_step_no already exists")

        # Add phase_type_code
        c2 = db.execute(text(
            "SELECT COUNT(*) FROM information_schema.columns "
            "WHERE table_schema=DATABASE() AND table_name='sku_steps' AND column_name='phase_type_code'"
        )).scalar()
        if c2 == 0:
            if not dry_run:
                db.execute(text(
                    "ALTER TABLE sku_steps ADD COLUMN phase_type_code TINYINT NOT NULL DEFAULT 0 "
                    "COMMENT 'Phase type 1-8: sent as DB15x0.RECIPE.Phase_Type to PLC'"
                ))
                db.commit()
                print("✅ Column phase_type_code added")
            else:
                print("[DRY] Would add column phase_type_code")
        else:
            print("ℹ️  Column phase_type_code already exists")

        # Load rows
        rows = db.execute(text(
            "SELECT id, phase_id, action_code, step_time, temperature, sub_step FROM sku_steps"
        )).fetchall()
        print(f"\n📊 Processing {len(rows)} rows...")

        updates = []
        type_summary = {}
        for r in rows:
            pid   = (r[1] or '').strip()
            step  = resolve_plc_step(r[1], r[2], r[3] or 0, r[4] or 0.0, r[5] or 0)
            ptype = PHASE_TYPE_MAP.get(pid, 0)
            updates.append({'id': r[0], 'step': step, 'ptype': ptype})
            key = f"{pid or 'NULL':<10} → Type {ptype}"
            type_summary[key] = type_summary.get(key, 0) + 1

        if not dry_run:
            for u in updates:
                db.execute(text(
                    "UPDATE sku_steps SET plc_step_no=:step, phase_type_code=:ptype WHERE id=:id"
                ), u)
            db.commit()
            print("✅ plc_step_no + phase_type_code populated")
        else:
            print("[DRY] Would update plc_step_no + phase_type_code")

        print("\n📋 phase_type_code Summary (ค่าที่ App จะส่งเป็น Phase_Type ไป PLC):")
        for k, v in sorted(type_summary.items()):
            print(f"  {k:<45} ({v} rows)")

        unknown = [u for u in updates if u['ptype'] == 0]
        if unknown:
            print(f"\n⚠️  {len(unknown)} rows phase_type_code=0 (unknown phase_id)")

    finally:
        db.close()


def validate():
    db = SessionLocal()
    try:
        rows = db.execute(text(
            "SELECT phase_id, phase_type_code, plc_step_no, COUNT(*) as cnt "
            "FROM sku_steps "
            "GROUP BY phase_id, phase_type_code, plc_step_no "
            "ORDER BY phase_type_code, plc_step_no"
        )).fetchall()
        print(f"\n  {'phase_id':<12}{'phase_type':<12}{'plc_step':<10}{'rows'}")
        print("-" * 45)
        for r in rows:
            print(f"  {r[0] or 'NULL':<12}{r[1]:<12}{r[2]:<10}{r[3]}")
    finally:
        db.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--validate', action='store_true')
    args = parser.parse_args()
    if args.validate:
        validate()
    else:
        run_migration(dry_run=args.dry_run)
