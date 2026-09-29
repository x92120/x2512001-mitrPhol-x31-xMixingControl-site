"""
seed_packing_sim.py — Seed prebatch reqs + recs for an EXISTING production plan
================================================================================
Targets: plan-Line-3-2026-03-04-001, Batch 001-010
Creates prebatch_reqs (ingredient requirements) and prebatch_recs (bags) for
each batch using real ingredients from the DB.

Run:  python3 seed_packing_sim.py
"""
import pymysql
import random
from datetime import datetime
from typing import Any, Dict, List, Tuple

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

PLAN_ID = "plan-Line-3-2026-03-04-001"
BATCH_START = 1
BATCH_END = 10

FALLBACK_FH = [
    {"re_code": "FH01", "name": "Flavour Vanilla",    "volume": 2.5},
    {"re_code": "FH02", "name": "Flavour Strawberry",  "volume": 1.8},
    {"re_code": "FH03", "name": "Flavour Chocolate",   "volume": 3.2},
]
FALLBACK_SPP = [
    {"re_code": "SPP01", "name": "Sugar Premix",       "volume": 12.0},
    {"re_code": "SPP02", "name": "Preservative P1",    "volume": 0.5},
    {"re_code": "SPP03", "name": "Color Agent C1",     "volume": 0.35},
]


def get_ingredients_by_wh(cur, wh: str, limit: int = 4) -> List[Dict[str, Any]]:
    cur.execute(
        "SELECT re_code, name FROM ingredients WHERE warehouse = %s AND status = 'Active' LIMIT %s",
        (wh, limit)
    )
    rows = cur.fetchall()
    return [{"re_code": r[0], "name": r[1]} for r in rows]


def clean_existing_reqs(cur, batch_db_ids: List[int]) -> None:
    """Remove existing prebatch reqs/recs for given batch db IDs."""
    for bid in batch_db_ids:
        # Delete rec_from first
        cur.execute("""
            DELETE prf FROM prebatch_rec_from prf
            JOIN prebatch_recs pr ON prf.prebatch_rec_id = pr.id
            JOIN prebatch_reqs pq ON pr.req_id = pq.id
            WHERE pq.batch_db_id = %s
        """, (bid,))
        # Delete recs
        cur.execute("""
            DELETE pr FROM prebatch_recs pr
            JOIN prebatch_reqs pq ON pr.req_id = pq.id
            WHERE pq.batch_db_id = %s
        """, (bid,))
        # Delete reqs
        cur.execute("DELETE FROM prebatch_reqs WHERE batch_db_id = %s", (bid,))


def main():
    print("=" * 65)
    print(f"🌱 Seeding PreBatch Sim Data for {PLAN_ID}")
    print(f"   Batches {BATCH_START:03d} to {BATCH_END:03d}")
    print("=" * 65)

    conn = pymysql.connect(**DB_CONFIG)
    cur = conn.cursor()

    try:
        # 1. Find the plan
        cur.execute("SELECT id FROM production_plans WHERE plan_id = %s", (PLAN_ID,))
        plan_row = cur.fetchone()
        if not plan_row:
            print(f"❌ Plan {PLAN_ID} not found!")
            return
        plan_db_id = plan_row[0]
        print(f"📋 Found plan db_id={plan_db_id}")

        # 2. Find batches 001-010
        cur.execute(
            "SELECT id, batch_id, status, batch_size FROM production_batches WHERE plan_id = %s ORDER BY batch_id",
            (plan_db_id,)
        )
        all_batches = cur.fetchall()
        print(f"   Total batches in plan: {len(all_batches)}")

        # Filter to batch 001-010
        target_batches = []
        for b in all_batches:
            suffix = b[1].split('-')[-1]  # e.g. "001"
            try:
                num = int(suffix)
                if BATCH_START <= num <= BATCH_END:
                    target_batches.append(b)
            except ValueError:
                continue

        print(f"   Target batches: {len(target_batches)}")
        if not target_batches:
            print("❌ No matching batches found!")
            return

        # 3. Get ingredients
        fh_ings = get_ingredients_by_wh(cur, 'FH', 4) or FALLBACK_FH
        spp_ings = get_ingredients_by_wh(cur, 'SPP', 4) or FALLBACK_SPP
        print(f"\n📦 Ingredients:")
        print(f"   FH : {[i['re_code'] for i in fh_ings]}")
        print(f"   SPP: {[i['re_code'] for i in spp_ings]}")

        # 4. Clean existing data
        batch_db_ids = [b[0] for b in target_batches]
        clean_existing_reqs(cur, batch_db_ids)
        print(f"\n🧹 Cleaned existing reqs/recs for {len(batch_db_ids)} batches")

        # 5. Seed reqs and recs for each batch
        batch_configs = []
        for i, b in enumerate(target_batches):
            batch_num = i + 1
            if batch_num <= 2:
                # Batches 1-2: Fully packed → Ready to Transfer
                cfg = {"packing_mode": "all", "status": "Prepared", "label": "✅ Ready"}
            elif batch_num <= 5:
                # Batches 3-5: Partially packed
                cfg = {"packing_mode": "partial", "status": "In-Progress", "label": "🟡 Partial"}
            else:
                # Batches 6-10: Not started
                cfg = {"packing_mode": "none", "status": "Created", "label": "⬜ None"}
            batch_configs.append((b, cfg))

        total_reqs = 0
        total_recs = 0

        for (batch_db_id, batch_id, _, batch_size), cfg in batch_configs:
            print(f"\n   🔹 {batch_id}  {cfg['label']}")

            # Update batch status
            cur.execute(
                "UPDATE production_batches SET status = %s WHERE id = %s",
                (cfg['status'], batch_db_id)
            )

            all_ings = [(ing, 'FH') for ing in fh_ings] + [(ing, 'SPP') for ing in spp_ings]
            for ing, wh in all_ings:
                # Random volume based on ingredient
                req_vol = round(random.uniform(1.0, 15.0), 2)

                # Req status
                if cfg['packing_mode'] == 'all':
                    req_status = 2
                elif cfg['packing_mode'] == 'partial':
                    req_status = random.choice([1, 2])
                else:
                    req_status = 0

                cur.execute("""
                    INSERT INTO prebatch_reqs
                    (batch_db_id, plan_id, batch_id, re_code, ingredient_name, required_volume, wh, status)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, (batch_db_id, PLAN_ID, batch_id,
                      ing['re_code'], ing['name'], round(req_vol, 4), wh, req_status))
                req_id = cur.lastrowid
                total_reqs += 1

                # Number of bags
                if cfg['packing_mode'] == 'none':
                    num_bags = random.choice([0, 1, 2])
                elif cfg['packing_mode'] == 'all':
                    num_bags = random.randint(2, 3)
                else:
                    num_bags = random.randint(1, 3)

                total_packages = max(num_bags, 1)

                for pkg_no in range(1, num_bags + 1):
                    bag_vol = round(req_vol / total_packages + random.uniform(-0.5, 0.5), 3)
                    bag_vol = max(0.1, bag_vol)
                    batch_record_id = f"{batch_id}-{ing['re_code']}-{pkg_no:03d}"
                    prebatch_id = f"{batch_id}{ing['re_code']}{pkg_no:03d}"
                    recode_batch_id = f"{pkg_no:03d}"

                    if cfg['packing_mode'] == 'all':
                        packing_status = 1
                    elif cfg['packing_mode'] == 'partial':
                        packing_status = random.choice([0, 0, 1])
                    else:
                        packing_status = 0

                    recheck = 1 if cfg['packing_mode'] == 'all' else (random.choice([0, 1]) if cfg['packing_mode'] == 'partial' else 0)

                    cur.execute("""
                        INSERT INTO prebatch_recs
                        (req_id, batch_record_id, plan_id, re_code, package_no, total_packages,
                         net_volume, total_volume, total_request_volume,
                         prebatch_id, recode_batch_id, recheck_status, packing_status)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (req_id, batch_record_id, PLAN_ID, ing['re_code'],
                          pkg_no, total_packages, bag_vol, bag_vol, req_vol,
                          prebatch_id, recode_batch_id, recheck, packing_status))
                    total_recs += 1

                bags_label = f"{num_bags} bags" if num_bags else "no bags"
                print(f"     • {ing['re_code']:12s} [{wh:3s}] {req_vol:7.2f}kg → {bags_label}")

        conn.commit()
        print(f"\n✅ Done! Created {total_reqs} reqs, {total_recs} recs for {len(target_batches)} batches")
        print("💾 All data committed!")

    except Exception as e:
        conn.rollback()
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        cur.close()
        conn.close()

    print("\n🎉 Refresh the Packing List page to see the data!")


if __name__ == "__main__":
    main()
