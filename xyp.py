# Service.py
# -*- coding: utf-8 -*-

from collections.abc import Mapping
import zeep, base64
from zeep import Client
from zeep.transports import Transport
from XypSign import XypSign
from requests import Session
import urllib3

# env.py-д доорх хувьсагчид заавал тодорхойло:
# ACCESS_TOKEN  = "Таны_өгөгдсөн_токен"
# CERT_PATH     = "/root/xyp/certificate.crt"   # эсвэл .pem файл бол тэр
# KEY_PATH      = "/root/xyp/mykey.key"
# REGNUM        = "ИХ97070415"                 # Таны иргэний регистрын дугаар
from env import ACCESS_TOKEN, CERT_PATH, KEY_PATH, REGNUM

class Service:
    """
    ХУР Төрийн Мэдээлэл Солилцооны системээс сервис дуудах класс.
    ------------------------------------------------------------------
    Хэрэглэх заавар:
        svc = Service(wsdl_url, timestamp)
        result = svc.get_vehicle_info("5705УКМ")
    ------------------------------------------------------------------
    """

    def __init__(self, wsdl_url: str, timestamp: str):
        """
        wsdl_url:  WSDL URL (жишээ: "https://xyp.gov.mn/transport-1.3.0/ws?WSDL")
        timestamp: milliseconds-тэй мөр, жишээ: str(int(time.time() * 1000))
        """
        # 1) ACCESS_TOKEN + timestamp дээр гарын үсэг үүсгэх
        signer = XypSign(KEY_PATH)
        # sign() нь (toBeSigned, signature) tuple буцаана; бидэнд зөвхөн signature хэрэгтэй
        _, self.__signature = signer.sign(ACCESS_TOKEN, timestamp)

        # 2) requests.Session үүсгэн, SSL шалгалтыг түр хасах, сертификат+private key-ээ тохируулах
        urllib3.disable_warnings()   # InsecureRequestWarning-ийг хаах
        session = Session()
        session.verify = False        # SSL шалгалтыг түр хасна (серверийн EKU асуудалтай үед ашиглах)
        session.cert = (CERT_PATH, KEY_PATH)

        # Zeep-д зориулсан Transport объект
        transport = Transport(session=session)

        # 3) Zeep Client үүсгэж, header-д accessToken, timeStamp, signature нэмэх
        self.client = Client(wsdl=wsdl_url, transport=transport)
        self.client.transport.session.headers.update({
            "accessToken": ACCESS_TOKEN,
            "timeStamp":   timestamp,
            "signature":   self.__signature
        })

    def deep_convert_unicode(self, key, layer):
        """
        Хэрвээ 'image' эсвэл 'driverPic' талбарын bytes ирвэл base64-р хөрвүүлэх
        (зарим WSDL operation-д зураг binary утга орж ирэх тохиолдолд хэрэг болно)
        """
        to_ret = layer
        if isinstance(layer, bytes) and key in ("image", "driverPic"):
            to_ret = base64.b64encode(layer)
        try:
            for k, v in to_ret.items():
                to_ret[k] = self.deep_convert_unicode(k, v)
        except AttributeError:
            pass
        return to_ret

    def deep_convert_dict(self, layer):
        """
        Хэрвээ nested bytes объект ирвэл dict болгож хөрвүүлэх
        """
        to_ret = layer
        if isinstance(layer, bytes):
            to_ret = dict(layer)
        try:
            for k, v in to_ret.items():
                to_ret[k] = self.deep_convert_dict(v)
        except AttributeError:
            pass
        return to_ret

    def get_vehicle_info(self, plate_number: str):
        """
        WS100401_getVehicleInfo operation жишээ

        plate_number: машины улсын дугаар (жишээ: "5705УКМ")
        ------------------------------------------------------------------
        resultCode:
            0 = Амжилттай
            3 = Хүчингүй хандалт (зөвшөөрөлгүй)
            бусад кодууд заавартай таарч өөрчилнө
        ------------------------------------------------------------------
        Жишээ нэвтрэх хүсэлт:
            {
                "auth": {
                    "citizen": {
                        "authType":        0,
                        "certFingerprint": "95B34F2C7E3A1C3B18D472A9563C1234567890AB",
                        "regnum":          REGNUM,
                        "signature":       self.__signature,
                        "civilId":         None,
                        "fingerprint":     b"*** NO ACCESS ***",
                        "appAuthToken":    None,
                        "authAppName":     None
                    },
                    "operator": {
                        "authType":        0,
                        "certFingerprint": None,
                        "regnum":          None,
                        "signature":       None,
                        "civilId":         None,
                        "fingerprint":     b"*** NO ACCESS ***",
                        "appAuthToken":    None,
                        "authAppName":     None
                    }
                },
                "cabinNumber":      None,
                "certificatNumber": None,
                "plateNumber":      "5705УКМ",
                "regnum":           None
            }
        """
        # 4) auth блокоор сертификатын fingerprint, подпись, regnum-ийг дамжуулах
        #    'certFingerprint' талд openssl-ээр авсан SHA1 fingerprint-ийг (колонуусгүй, бүх үсэг их) бичнэ.
        auth_block = {
            "citizen": {
                "authType":        0,  # 0 = сертификатаар баталгаажуулна
                "certFingerprint": "95B34F2C7E3A1C3B18D472A9563C1234567890AB",
                "regnum":          REGNUM,
                "signature":       self.__signature,
                "civilId":         None,
                "fingerprint":     b"*** NO ACCESS ***",
                "appAuthToken":    None,
                "authAppName":     None
            },
            "operator": {
                "authType":        0,
                "certFingerprint": None,
                "regnum":          None,
                "signature":       None,
                "civilId":         None,
                "fingerprint":     b"*** NO ACCESS ***",
                "appAuthToken":    None,
                "authAppName":     None
            }
        }

        # 5) Request параметрүүд
        params = {
            "auth":            auth_block,
            "cabinNumber":     None,
            "certificatNumber": None,
            "plateNumber":     plate_number,
            "regnum":          None
        }

        # 6) WS100401_getVehicleInfo үйлдлийг дуудаж, хариуг авах
        try:
            response = self.client.service.WS100401_getVehicleInfo(params)
            return response
        except Exception as e:
            print(f"WS100401_getVehicleInfo алдаа: {e}")
            return None

if __name__ == "__main__":
    import time

    # 7) Жишээ ашиглалт
    #    - wsdl_url-д WSDL эндпоинтыг зааж өгнө
    #    - timestamp-д milliseconds-тэй тэмдэгт өгнө
    wsdl_url = "https://xyp.gov.mn/transport-1.3.0/ws?WSDL"
    timestamp = str(int(time.time() * 1000))

    svc = Service(wsdl_url, timestamp)
    result = svc.get_vehicle_info("5705УКМ")
    print("Хариу:", result)
