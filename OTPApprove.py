from XypClient import Service
from env import KEY_PATH
from env import REGNUM
import time


"""
OTP авах амжилттай болсон тохиолдолд иргэнд ирсэн кодыг ашиглаж сервис дуудах
@param OTPNumber иргэний утсанд ирсэн баталгаажуулах код

@author unenbat
@since 2023-05-23
"""


def CallXYPService():
    params = {
        'auth': None,
        'regnum': REGNUM,
    }
    citizen = Service('https://xyp.gov.mn/property-1.3.0/ws?WSDL',
                      str(int(time.time())), pkey_path=KEY_PATH)
    citizen.dump('WS100202_getPropertyList', params)


if __name__ == "__main__":
    CallXYPService()
