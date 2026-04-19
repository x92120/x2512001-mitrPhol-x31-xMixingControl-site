"""
seed_packinglist.py — Re-seed simulation data for x50-PackingList testing
=========================================================================
Creates:
  - 1 production plan (PL-PKL-TEST-001) with 5 batches
  - prebatch_reqs per batch (FH + SPP ingredients)
  - prebatch_recs (bags) per requirement — mix of packed/unpacked
  - Batches 001 & 002 are fully packed → Ready to Transfer
  - Batches 003 & 004 are partially packed → In-Progress
  - Batch 005 is not started
  
Run:  python3 seed_packinglist.py
"""
import pymysql  # type: ignore[import-untyped]
import random
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

DB_CONFIG = dict(
    host='152.42.166.150',
    port=3306,
    user='mixingcontrol',
    password='admin100',
    database='xMixingControl',
    connect_timeout=30,
    read_timeout=30,
    write_timeout=30,
    autocommit=False,
)

PLAN_ID = "PL-PKL-TEST-001"
SKU_ID: Optional[str] = None
NUM_BATCHES: int = 5

FALLBACK_FH: List[Dict[str, Any]] = [
    {"re_code": "FH01", "name": "Flavour Vanilla",     "volume": 2.5},
    {"re_code": "FH02", "name": "Flavour Strawberry",  "volume": 1.8},
    {"re_code": "FH03", "name": "Flavour Chocolate",   "volume": 3.2},
]
FALLBACK_SPP: List[Dict[str, Any]] = [
    {"re_code": "SPP01", "name": "Sugar Premix",       "volume": 12.0},
    {"re_code": "SPP02", "name": "Preservative P1",    "volume": 0.5},
    {"re_code": "SPP03", "name": "Color Agent C1",     "volume": 0.35},
]


def clean_old_data(cur: Any) -> None:
    print("🧹 Cleaning old PL-PKL-TEST data...")
    cur.execute("SELECT id FROM production_plans WHERE plan_id = %s", (PLAN_ID,))
    plan = cur.fetchone()
    if not plan:
        print("   No old data found — skipping cleanup")
        return
    plan_db_id = plan[0]
    cur.execute("SELECT id, batch_id FROM production_batches WHERE plan_id = %s", (plan_db_id,))
    batches = cur.fetchall()
    for batch_db_id, batch_id in batches:
        cur.execute("""
            DELETE prf FROM prebatch_rec_from prf
            JOIN prebatch_recs pr ON prf.prebatch_rec_id = pr.id
            JOIN prebatch_reqs pq ON pr.req_id = pq.id
            WHERE pq.batch_db_id = %s
        """, (batch_db_id,))
        cur.execute("""
            DELETE pr FROM prebatch_recs pr
            JOIN prebatch_reqs pq ON pr.req_id = pq.id
            WHERE pq.batch_db_id = %s
        """, (batch_db_id,))
        cur.execute("DELETE FROM prebatch_reqs WHERE batch_db_id = %s", (batch_db_id,))
        cur.execute("DELETE FROM prebatch_items WHERE batch_db_id = %s", (batch_db_id,))
    cur.execute("DELETE FROM production_batches WHERE plan_id = %s", (plan_db_id,))
    cur.execute("DELETE FROM production_plans WHERE id = %s", (plan_db_id,))
    print(f"   ✅ Cleaned {len(batches)} old batches")


def get_ingredients_by_wh(cur: Any, wh: str, limit: int = 4) -> List[Dict[str, Any]]:
    cur.execute(
        "SELECT re_code, name FROM ingredients WHERE warehouse = %s AND status = 'Active' LIMIT %s",
        (wh, limit)
    )
    rows = cur.fetchall()
    return [{"re_code": r[0], "name": r[1]} for r in rows]


def get_sku(cur: Any) -> Tuple[str, str, float]:
    cur.execute("SELECT sku_id, sku_name, std_batch_size FROM sku_masters WHERE status = 'Active' LIMIT 1")
    row = cur.fetchone()
    if row:
        return str(row[0]), str(row[1]), float(row[2] or 500.0)
    return "SKU-TEST-001", "Test SKU", 500.0


def seed_data(cur: Any) -> None:
    sku_id, sku_name, batch_size = get_sku(cur)
    print(f"📦 Using SKU: {sku_id} ({sku_name}), batch_size={batch_size}")

    fh_ings = get_ingredients_by_wh(cur, 'FH', 3) or FALLBACK_FH
    spp_ings = get_ingredients_by_wh(cur, 'SPP', 3) or FALLBACK_SPP
    print(f"   FH : {[i['re_code'] for i in fh_ings]}")
    print(f"   SPP: {[i['re_code'] for i in spp_ings]}")

    cur.execute("""
        INSERT INTO production_plans
        (plan_id, sku_id, sku_name, plant, total_volume, batch_size, num_batches,
         status, batch_prepare, created_by)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, (PLAN_ID, sku_id, sku_name, 'Line-1',
          batch_size * NUM_BATCHES, batch_size, NUM_BATCHES,
          'In-Progress', False, 'seed_script'))
    plan_db_id = cur.lastrowid
    print(f"\n📋 Created plan: {PLAN_ID} (db_id={plan_db_id})")

    # packing_mode:
    #   'all'     → all bags packing_status=1  ✅ Ready to Transfer
    #   'partial' → random mix
    #   'none'    → all packing_status=0
    batch_configs = [
        {"suffix": "001", "status": "Prepared",    "batch_prepare": True,  "rec_complete": True,  "packing_mode": "all",     "label": "✅ Ready to Transfer"},
        {"suffix": "002", "status": "Prepared",    "batch_prepare": True,  "rec_complete": True,  "packing_mode": "all",     "label": "✅ Ready to Transfer"},
        {"suffix": "003", "status": "In-Progress", "batch_prepare": False, "rec_complete": False, "packing_mode": "partial", "label": "🟡 Partially Packed"},
        {"suffix": "004", "status": "In-Progress", "batch_prepare": False, "rec_complete": False, "packing_mode": "partial", "label": "🟡 Partially Packed"},
        {"suffix": "005", "status": "Created",     "batch_prepare": False, "rec_complete": False, "packing_mode": "none",    "label": "⬜ Not Started"},
    ]

    for cfg in batch_configs:
        batch_id = f"{PLAN_ID}-{cfg['suffix']}"
        cur.execute("""
            INSERT INTO production_batches
            (plan_id, batch_id, sku_id, plant, batch_size, status, batch_prepare)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (plan_db_id, batch_id, sku_id, 'Line-1', batch_size, cfg['status'], cfg['batch_prepare']))
        batch_db_id = cur.lastrowid
        print(f"\n   🔹 {batch_id}  {cfg['label']}")

        all_ings = [(ing, 'FH') for ing in fh_ings] + [(ing, 'SPP') for ing in spp_ings]
        for ing, wh in all_ings:
            req_vol: float = float(ing.get('volume') or round(random.uniform(1.0, 15.0), 2))

            if cfg['rec_complete']:
                req_status = 2
            elif cfg['status'] == 'In-Progress':
                req_status = random.choice([1, 2])
            else:
                req_status = random.choice([0, 1])

            cur.execute("""
                INSERT INTO prebatch_reqs
                (batch_db_id, plan_id, batch_id, re_code, ingredient_name, required_volume, wh, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (batch_db_id, PLAN_ID, batch_id,
                  ing['re_code'], ing['name'], round(req_vol, 4), wh, req_status))
            req_id = cur.lastrowid

            if cfg['packing_mode'] == 'none' and random.random() < 0.4:
                num_bags = 0
            elif cfg['rec_complete']:
                num_bags = random.randint(2, 3)
            else:
                num_bags = random.randint(1, 2)

            total_packages: int = max(num_bags, 1)

            for pkg_no in range(1, num_bags + 1):
                bag_vol = round(req_vol / total_packages + random.uniform(-0.5, 0.5), 3)
                bag_vol = max(0.1, bag_vol)
                batch_record_id = f"{batch_id}-{ing['re_code']}-{pkg_no:03d}"
                prebatch_id     = f"{batch_id}{ing['re_code']}{pkg_no:03d}"
                recode_batch_id = f"{pkg_no:03d}"

                if cfg['packing_mode'] == 'all':
                    packing_status = 1
                elif cfg['packing_mode'] == 'partial':
                    packing_status = random.choice([0, 0, 1])
                else:
                    packing_status = 0

                recheck_status = 1 if cfg['rec_complete'] else random.choice([0, 1]) if cfg['status'] == 'In-Progress' else 0

                cur.execute("""
                    INSERT INTO prebatch_recs
                    (req_id, batch_record_id, plan_id, re_code, package_no, total_packages,
                     net_volume, total_volume, total_request_volume,
                     prebatch_id, recode_batch_id, recheck_status, packing_status)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (req_id, batch_record_id, PLAN_ID, ing['re_code'],
                      pkg_no, total_packages, bag_vol, bag_vol, req_vol,
                      prebatch_id, recode_batch_id, recheck_status, packing_status))

            pack_icon = '✅' if cfg['packing_mode'] == 'all' else ('⚡' if cfg['packing_mode'] == 'partial' else '⬜')
            bags_label = f"{num_bags} bags" if num_bags else "no bags yet"
            print(f"     • {ing['re_code']:8s} [{wh}] {req_vol:7.2f}kg → {bags_label} {pack_icon}")

    print("\n✅ Seed complete!")


def main() -> None:
    print("=" * 65)
    print("🌱 Packing List Seed v2  —  with Ready-to-Transfer batches")
    print("=" * 65)

    conn = pymysql.connect(**DB_CONFIG)
    cur  = conn.cursor()
    try:
        clean_old_data(cur)
        seed_data(cur)
        conn.commit()
        print("\n💾 All data committed!")
    except Exception as e:
        conn.rollback()
        print(f"\n❌ Error: {e}")
        raise
    finally:
        cur.close()
        conn.close()

    # ── Verification ────────────────────────────────────────────────
    print("\n" + "=" * 65)
    print("🔍 Verification")
    print("=" * 65)
    conn = pymysql.connect(**DB_CONFIG)
    cur  = conn.cursor()

    cur.execute("""
        SELECT pb.batch_id, pb.status, pb.batch_prepare,
               COALESCE(SUM(pr.packing_status), 0) as packed,
               COUNT(pr.id) as total
        FROM production_batches pb
        JOIN production_plans pp ON pb.plan_id = pp.id
        LEFT JOIN prebatch_reqs pq ON pq.batch_db_id = pb.id
        LEFT JOIN prebatch_recs pr  ON pr.req_id = pq.id
        WHERE pp.plan_id = %s
        GROUP BY pb.batch_id, pb.status, pb.batch_prepare
        ORDER BY pb.batch_id
    """, (PLAN_ID,))
    print("\n   Batch Summary:")
    for r in cur.fetchall():
        ready = "✅ Ready to Transfer" if r[2] else ""
        print(f"   {r[0]:38s}  {r[1]:12s}  packed={r[3]}/{r[4]}  {ready}")

    cur.close()
    conn.close()
    print("\n🎉 Done!  Open the Packing List page to test.")


if __name__ == "__main__":
    main()
