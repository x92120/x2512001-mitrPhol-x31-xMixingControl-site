from database import SessionLocal
from models import PreBatchItem, ProductionBatch
import uuid

db = SessionLocal()
batch = db.query(ProductionBatch).filter(ProductionBatch.batch_id == "P-SIM-03110006-B01").first()

if batch:
    batch.fh_delivered_at = None
    batch.spp_delivered_at = None

    for i in range(1, 31):
        item = PreBatchItem(
            batch_db_id=batch.id,
            plan_id=batch.plan_id,
            batch_id=batch.batch_id,
            re_code="DUMMY_FH_" + str(i).zfill(2),
            ingredient_name="Dummy Flavour " + str(i),
            required_volume=0.5,
            wh="FH",
            status=2,
            batch_record_id="PKG-SIM-" + str(i).zfill(2),
            net_volume=0.5,
            package_no=1,
            total_packages=1,
            packing_status=0,
            prebatch_id="PB-SIM-03110006-B01-FH-" + str(i).zfill(2)
        )
        db.add(item)
    db.commit()
    print("Added 30 UNPACKED dummy FH items to P-SIM-03110006-B01 to test Current Box flow.")
else:
    print("Batch not found.")
db.close()
