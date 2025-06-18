import time 
import os
from client import Service



params = {}
params.update({"plateNumber": "0892УБЛ"})

try:
    key_path = "/root/xyp/mykey.key"
    print("KEY_PATH: ", key_path)

    # if prod
    timestamp = str(int(time.time()))
    citizen = Service(
        "https://xyp.gov.mn/transport-1.3.0/ws?WSDL", timestamp, pkey_path=key_path)
    res = citizen.dump("WS100401_getVehicleInfo", params)
    print(res)
except Exception as e:
    print(e)
