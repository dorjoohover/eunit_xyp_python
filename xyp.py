import time 
import os
from client import Service

from env import REGNUM

params = {}
# params.update({"plateNumber": "0892УБЛ"})
params.update({"regnum": REGNUM })

try:
    key_path = "/root/xyp/mykey.key"
    print("KEY_PATH: ", key_path)

    # if prod
    timestamp = str(int(time.time()))
    citizen = Service(
        # "https://xyp.gov.mn/transport-1.3.0/ws?WSDL", timestamp, pkey_path=key_path)
        "https://xyp.gov.mn/property-1.3.0/ws?WSDL", timestamp, pkey_path=key_path)
        
    # res = citizen.dump("WS100401_getVehicleInfo", params)
    res = citizen.dump("WS100202_getPropertyList", params)
    
    print(res)
except Exception as e:
    print(e)
