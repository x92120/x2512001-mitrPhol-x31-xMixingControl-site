import sys
sys.path.append('/home/x-root/xApp/x2512001-mitrPhol-x31-xMixingControl/x3101-app/x3101-0210-backEnd/x0201-fastAPI')
from database import SessionLocal
import models
db = SessionLocal()
step = db.query(models.SkuStep).filter(models.SkuStep.require.like('446.05%')).first()
if step:
    print(f"Step ID: {step.id}, Phase: {step.phase_number}, SubStep: {step.sub_step}")
    print(f"Action: {step.action_code}, ReCode: {step.re_code}, Require: {step.require}")
else:
    print("Not found")

step2 = db.query(models.SkuStep).filter(models.SkuStep.require > 446, models.SkuStep.require < 447).first()
if step2:
    print("Found step2:", step2.action_code, step2.re_code, step2.require)
