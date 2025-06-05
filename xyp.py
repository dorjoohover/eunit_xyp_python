from client import Service
import time

wsdl_url = "https://xyp.gov.mn/transport-1.3.0/ws?WSDL"
timestamp = str(int(time.time() * 1000))
svc = Service(wsdl_url, timestamp, pkey_path=KEY_PATH)

# жишээ operation-д дамжуулах параметр
params = {
    "param1": "value1",
    "param2": "value2"
}

result = svc.dump("WS100401_getVehicleInfo", params)
print("Result:", result)