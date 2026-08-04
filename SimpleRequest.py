import time
from zeep.helpers import serialize_object

from XypClient import Service
from env import KEY_PATH

service = Service(
    "https://xyp.gov.mn/transport-1.3.0/ws?WSDL",
    str(int(time.time())),
    pkey_path=KEY_PATH,
)

result = service.client.service.WS100401_getVehicleInfo({
    "plateNumber": "4836УАТ",
})

print(serialize_object(result))