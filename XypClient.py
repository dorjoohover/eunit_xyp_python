# Service.py
# -- coding: utf-8 --

from collections.abc import Mapping
import zeep, base64
from zeep import Client
from zeep.transports import Transport
from XypSign import XypSign
from requests import Session
import urllib3

# env.py дотор:
# ACCESS_TOKEN = "..."       # танай өгөгдсөн токен
# CERT_PATH    = "/path/to/your/certificate.crt"
# KEY_PATH     = "/path/to/your/private.key"
from env import ACCESS_TOKEN, CERT_PATH, KEY_PATH

"""
ХУР Төрийн Мэдээлэл Солилцооны системээс сервис дуудах 

@author unenbat
@since 2023-05-23
"""
class Service():
    def __init__(self, wsdl, timestamp, pkey_path=None):
        # --------------------------------------------------------------------
        # 1) XypSign ашиглан ACCESS_TOKEN + timestamp дээр гарын үсэг (signature) үүсгэнэ
        # --------------------------------------------------------------------
        print("timestamp: ", timestamp)
        self.__accessToken = ACCESS_TOKEN
        # pkey_path нь private key-ийн зам. XypSign-д энэ замыг дамжуулна.
        self.__toBeSigned, self.__signature = XypSign(pkey_path).sign(self.__accessToken, timestamp)
        
        # --------------------------------------------------------------------
        # 2) requests.Session үүсгэж, client сертификат + түлхүүрийг тохируулна
        # --------------------------------------------------------------------
        urllib3.disable_warnings()   # SSL сэрэмжлүүлгийг хаах
        session = Session()
        session.verify = False       # SSL сертификатын шалгалтыг алгасах (хэрвээ тохируулах шаардлагагүй бол True болгох)
        
        # энд яг сертификат+түлхүүрийн замыг дамжуулж байна:
        #   CERT_PATH = "/home/eunit/xyp/certificate.crt"
        #   KEY_PATH  = "/home/eunit/xyp/private.key"
        session.cert = (CERT_PATH, KEY_PATH)
        
        # Zeep-д зориулсан Transport объект
        transport = zeep.Transport(session=session)
        
        # --------------------------------------------------------------------
        # 3) Zeep Client үүсгэж, header-д accessToken, timeStamp, signature нэмнэ
        # --------------------------------------------------------------------
        self.client = zeep.Client(wsdl, transport=transport)
        self.client.transport.session.headers.update({
            'accessToken': self.__accessToken,
            'timeStamp'  : timestamp,
            'signature'  : self.__signature
        })
    
    def deep_convert_unicode(self, key, layer):
        to_ret = layer
        if isinstance(layer, bytes) and (key == 'image' or key == 'driverPic'):
            to_ret = base64.b64encode(layer)
        try:
            for k, v in to_ret.items():
                to_ret[k] = self.deep_convert_unicode(k, v)
        except AttributeError:
            pass
        return to_ret
        
    def deep_convert_dict(self,  layer):
        to_ret = layer
        if isinstance(layer, bytes):
            to_ret = dict(layer)
        try:
            for k, v in to_ret.items():
                to_ret[k] = self.deep_convert_dict(v)
        except AttributeError:
            pass
        return to_ret
    
    def dump(self, operation, params=None):
        """
        operation: WS100401_getVehicleInfo гэх мэт operation нэр
        params:    dict хэлбэртэй параметрүүд
        """
        try:
            if params:
                print(params)
                response = self.client.service[operation](params)
                print(response)
                return response
            else:
                res = self.client.service[operation]()
                print(res)
                return res
        except Exception as e:
            print(operation, str(e))
            return None
