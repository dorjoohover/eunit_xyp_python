from XypClient import Service
from env import KEY_PATH
from env import REGNUM
import time
import os


"""
OTP авах амжилттай болсон тохиолдолд иргэнд ирсэн кодыг ашиглаж сервис дуудах
@param OTPNumber иргэний утсанд ирсэн баталгаажуулах код

@author unenbat
@since 2023-05-23
"""


def CallXYPService():
    key_path = os.getenv("KEY_PATH")
    print("KEY_PATH: ", key_path)
    params = {
        'auth': None,
        'regnum': REGNUM,
        "plateNumber": '5705УКМ'
    }
    timestamp = str(int(time.time()))

    citizen = Service(
        "https://xyp.gov.mn/transport-1.3.0/ws?WSDL", timestamp, pkey_path=KEY_PATH)
    res = citizen.dump("WS100401_getVehicleInfo", params)
    print(res)
    return res


if __name__ == "__main__":
    CallXYPService()
