from sqlalchemy import create_engine
import time

url = "mysql+pymysql://mixingcontrol:admin100@152.42.166.150:3306/xMixingControl?ssl_disabled=true"
engine = create_engine(url)
t0 = time.time()
try:
    with engine.connect() as conn:
        print("Connected with ssl_disabled=true in", time.time() - t0)
except Exception as e:
    print("Failed with ssl_disabled=true:", e)

url2 = "mysql+pymysql://mixingcontrol:admin100@152.42.166.150:3306/xMixingControl"
engine2 = create_engine(url2, connect_args={"ssl": False})
t0 = time.time()
try:
    with engine2.connect() as conn:
        print("Connected with connect_args={'ssl': False} in", time.time() - t0)
except Exception as e:
    print("Failed with connect_args={'ssl': False}:", e)
