from XypClient import Service
from env import KEY_PATH
from env import REGNUM, ACCESS_TOKEN
import time
from XypSign import XypSign


"""
OTP авах амжилттай болсон тохиолдолд иргэнд ирсэн кодыг ашиглаж сервис дуудах
@param OTPNumber иргэний утсанд ирсэн баталгаажуулах код

@author unenbat
@since 2023-05-23
"""
timestamp = str(int(time.time() * 1000))

def CallXYPService(OTPNumber):
    signer_citizen = XypSign(KEY_PATH)
    _, sig_citizen = signer_citizen.sign(ACCESS_TOKEN, timestamp)
    params = {
        'auth': {
            'citizen': {
                'certFingerprint': "95B3A82A5AE64C208CFAED0D56B7563C",
                'regnum': REGNUM,
                'signature': "",
                'appAuthToken': None,
                'authAppName': None,
                'civilId': "",
                'fingerprint': "95B3A82A5AE64C208CFAED0D56B7563C",
                'otp': OTPNumber,
            },
            'operator': {
                'appAuthToken': None,
                'authAppName': None,
                'certFingerprint': None,
                'civilId': None,
                'fingerprint': "95B3A82A5AE64C208CFAED0D56B7563C",
                'otp': None,
                'regnum': None,
                'signature': None
            }
        },
        'plateNumber': '5705УКМ',
        'regnum': REGNUM
    }
    citizen = Service('https://xyp.gov.mn/transport-1.3.0/ws?WSDL',
                      str(int(time.time())), pkey_path=KEY_PATH)
    citizen.dump('WS100401_getVehicleInfo', params)


"""
OTP код авах WS100008_registerOTPRequest сервисийг ашиглаж WS100401_getVehicleInfo сервисийг ашиглах хүсэлтийг sms-ээр явуулах

@author unenbat
@since 2023-05-23
"""


def OTPservice():
    params = {
        'auth': {
            'citizen': {
                'certFingerprint': None,
                'regnum': REGNUM,
                'signature': None,
                'appAuthToken': None,
                'authAppName': None,
                'civilId': None,
                'fingerprint': b'*** NO ACCESS ***',
                'otp': 0,
            },
            'operator': {
                'appAuthToken': None,
                'authAppName': None,
                'certFingerprint': None,
                'civilId': None,
                'fingerprint': b'*** NO ACCESS ***',
                'otp': 0,
                'regnum': None,
                'signature': None
            }
        },
        'regnum': REGNUM,
        'jsonWSList': "[{\"ws\":\"WS100401_getVehicleInfo\"}]",
        'isSms': 1,
        'isApp': 0,
        'isEmail': 0,
        'isKiosk': 0,
        # 'phoneNum': 95992333,
        'phoneNum': 0,
        "plateNumber": '5705УКМ'
    }
    citizen = Service('https://xyp.gov.mn/meta-1.5.0/ws?WSDL',
                      str(int(time.time())), pkey_path=KEY_PATH)
    citizen.dump('WS100008_registerOTPRequest', params)
    print("-----------------------------------------------------------")
    print("-----------------------------------------------------------")
    OTPMessageNumber = int(input("Иргэнд ирсэн OTP кодыг оруулна уу: "))
    CallXYPService(OTPMessageNumber)


if __name__ == "__main__":
    OTPservice()
