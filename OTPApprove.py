
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
        'plateNumber': '5705УКМ'
    }
    print(params)
    print('https://xyp.gov.mn/transport-1.3.0/ws?WSDL',
          str(int(time.time())), pkey_path=KEY_PATH)
    citizen = Service('https://xyp.gov.mn/transport-1.3.0/ws?WSDL',
                      str(int(time.time())), pkey_path=KEY_PATH)
    res = citizen.dump('WS100401_getVehicleInfo', params)
    print(res)
    return res


"""
OTP код авах WS100008_registerOTPRequest сервисийг ашиглаж WS100101_getCitizenIDCardInfo сервисийг ашиглах хүсэлтийг sms-ээр явуулах

@author unenbat
@since 2023-05-23
"""


if __name__ == "__main__":
    CallXYPService()
