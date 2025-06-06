# otp_vehicle.py
# -*- coding: utf-8 -*-

import time
from XypClient import Service
from env import KEY_PATH, REGNUM

def request_otp():
    timestamp = str(int(time.time() * 1000))
    ws = Service("https://xyp.gov.mn/meta-1.5.0/ws?WSDL", timestamp, pkey_path=KEY_PATH)

    params = {
        'auth': {
            'citizen': {
                'authType':        1,
                'certFingerprint': None,
                'regnum':          REGNUM,
                'signature':       None,
                'civilId':         None,
                'fingerprint':     b'*** NO ACCESS ***',
                'appAuthToken':    None,
                'authAppName':     None,
                'otp':             0
            },
            'operator': {
                'authType':        1,
                'certFingerprint': None,
                'regnum':          None,
                'signature':       None,
                'civilId':         None,
                'fingerprint':     b'*** NO ACCESS ***',
                'appAuthToken':    None,
                'authAppName':     None,
                'otp':             0
            }
        },
        'regnum':     REGNUM,
        'jsonWSList': '[{"ws":"WS100401_getVehicleInfo"}]',
        'isSms':      1,
        'isApp':      0,
        'isEmail':    0,
        'isKiosk':    0,
        'phoneNum':   0
    }

    return ws.dump('WS100008_registerOTPRequest', params)


def get_vehicle_info(otp_code: int):
    timestamp = str(int(time.time() * 1000))
    ws = Service("https://xyp.gov.mn/transport-1.3.0/ws?WSDL", timestamp, pkey_path=KEY_PATH)

    params = {
        'auth': {
            'citizen': {
                'authType':        1,
                'certFingerprint': None,
                'regnum':          REGNUM,
                'signature':       None,
                'civilId':         None,
                'fingerprint':     b'*** NO ACCESS ***',
                'appAuthToken':    None,
                'authAppName':     None,
                'otp':             otp_code
            },
            'operator': {
                'authType':        1,
                'certFingerprint': None,
                'regnum':          None,
                'signature':       None,
                'civilId':         None,
                'fingerprint':     b'*** NO ACCESS ***',
                'appAuthToken':    None,
                'authAppName':     None,
                'otp':             0
            }
        },
        'cabinNumber':      None,
        'certificatNumber': None,
        'plateNumber':      '5705УКМ',
        'regnum':           REGNUM
    }

    return ws.dump('WS100401_getVehicleInfo', params)


if __name__ == "__main__":
    # 1) OTP авах
    otp_response = request_otp()
    print("OTP request response:")
    print(otp_response)
    print("--------------------------------------------------")

    # 2) Хэрвээ OTP-г илгээсэн бол хэрэглэгчээс код асууж, машин мэдээлэл авах
    otp_code = int(input("Иргэнд ирсэн OTP кодыг оруулна уу: ").strip())
    vehicle_response = get_vehicle_info(otp_code)
    print("Vehicle info response:")
    print(vehicle_response)
