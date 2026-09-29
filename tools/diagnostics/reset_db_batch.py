import sys
sys.path.append('/home/x-root/xApp/x2512001-mitrPhol-x31-xMixingControl/x3101-app/x3101-0210-backEnd/x0201-fastAPI')
from database import SessionLocal
from sqlalchemy import text

db = SessionLocal()
db.execute(text("UPDATE production_batches SET done = 0, status = 'Pending' WHERE batch_id = 'P260626-02-02-002'"))
db.commit()
print("Batch P260626-02-02-002 reset successfully in MySQL database!")
