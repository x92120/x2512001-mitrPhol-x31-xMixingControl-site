import sys
sys.path.append('/home/x-root/xApp/x2512001-mitrPhol-x31-xMixingControl/x3101-app/x3101-0210-backEnd/x0201-fastAPI')
from database import SessionLocal
import models
db = SessionLocal()
steps = db.query(models.SkuStep).filter(models.SkuStep.require > 400).limit(5).all()
for s in steps:
    print(s.action_code, s.re_code, s.require)
