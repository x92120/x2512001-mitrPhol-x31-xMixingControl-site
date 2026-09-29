import sys
sys.path.append('/home/x-root/xApp/x2512001-mitrPhol-x31-xMixingControl/x3101-app/x3101-0210-backEnd/x0201-fastAPI')
from plc_service import plc

for db_num in [1510, 1512, 1513, 1520, 1522, 1530]:
    data = plc.db_read(db_num, 0, 10)
    if data:
        print(f"DB{db_num} read success!")
    else:
        print(f"DB{db_num} read failed")
