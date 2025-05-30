from XypClient import Service
from env import REGNUM
from env import KEY_PATH
import time


"""
OTP авах амжилттай болсон тохиолдолд иргэнд ирсэн кодыг ашиглаж сервис дуудах
@param OTPNumber иргэний утсанд ирсэн баталгаажуулах код

@author unenbat
@since 2023-05-23
"""
def CallXYPService(OTPNumber):
    params = {  
        'auth': {
                # 'citizen': {
                #     'certFingerprint': None,
                #     'regnum': REGNUM,
                #     'signature': None,
                #     'appAuthToken': None,
                #     'authAppName': None,                
                #     'civilId': None,
                #     'fingerprint': b'*** NO ACCESS ***',
                #     'otp': OTPNumber,
                # },
                'operator': {
                    'appAuthToken': None,
                    'authAppName': None,
                    'certFingerprint': None,
                    'civilId': None,
                    'fingerprint': b'*** NO ACCESS ***',
                    'otp': OTPNumber,
                    'regnum': None,
                    'signature': None
                }
            },
            'regnum': REGNUM,
        }
    
    # citizen = Service('https://xyp.gov.mn/property-1.3.0/ws?WSDL', str(int(time.time())) , pkey_path=key_path)
    # citizen.dump('WS100202_getPropertyList', params)

"""
OTP код авах WS100008_registerOTPRequest сервисийг ашиглаж WS100101_getCitizenIDCardInfo сервисийг ашиглах хүсэлтийг sms-ээр явуулах

@author unenbat
@since 2023-05-23
"""
def OTPservice():
    params = {  
        
        }
    timestamp = str(int(time.time()))
    params.update({'plateNumber': '5705УКМ'})
    try:
        citizen = Service('https://xyp.gov.mn/transport-1.3.0/ws?WSDL', timestamp , pkey_path=KEY_PATH)
        res = citizen.dump('WS100401_getVehicleInfo', params)
        print(res)
    except Exception as e: 
        print(e)
    
if __name__ == "__main__":
    OTPservice()
    