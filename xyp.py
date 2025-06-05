# Service.py
# -*- coding: utf-8 -*-

import time
import base64
import zeep
from zeep import Client
from zeep.transports import Transport
from requests import Session
import urllib3

from XypSign import XypSign
from env import ACCESS_TOKEN, CERT_PATH, KEY_PATH, REGNUM


class Service:
    """
    ХУР Төрийн Мэдээлэл Солилцооны системээс SOAP сервис дуудахын тулд ашиглана.
    """

    def __init__(self, wsdl_url: str, timestamp: str):
        """
        wsdl_url:  WSDL эндпоинтын URL (жишээ: "https://xyp.gov.mn/transport-1.3.0/ws?WSDL")
        timestamp: milliseconds-тэй мөр, жишээ: str(int(time.time() * 1000))
        """

        # 1) ACCESS_TOKEN + timestamp дээр подпись (signature) үүсгэх
        #    - Хамгийн гол нь ACCESS_TOKEN бол XYP-с танд өгсөн "жинхэнэ токен" байх ёстой.
        #    - Хэрвээ ACCESS_TOKEN-д та "сертификатын fingerprint" өгсөн бол сервер таныг танихгүй, "хүчингүй хандалт" (resultCode = 3) өгнө.
        signer = XypSign(KEY_PATH)
        to_be_signed, signature = signer.sign(ACCESS_TOKEN, timestamp)

        # Debug хэвлэх (иш татах зориудаар; шаардлагагүй бол устгана)
        print("---- DEBUG ----")
        print("ToBeSigned:", to_be_signed)
        print("Signature:", signature)
        print("----------------")
        self.__signature = signature

        # 2) requests.Session үүсгэж, SSL шалгалтыг түр хасах, сертификат+private key-ээ тохируулах
        #    - "session.verify = False" нь curl -k (–insecure)-тэй адил, SSL/TLS шалгалтыг түр тасалж холбогдоно.
        #    - Хэрвээ xyp.gov.mn серверийн сертификатын EKU-г бүрэн зөв зассан бол "session.verify = True" болгож болно.
        urllib3.disable_warnings()
        session = Session()
        session.verify = False
        session.cert = (CERT_PATH, KEY_PATH)

        transport = Transport(session=session)

        # 3) Zeep Client үүсгэж, HTTP header-д accessToken, timeStamp, signature нэмэх
        self.client = Client(wsdl=wsdl_url, transport=transport)
        self.client.transport.session.headers.update({
            "accessToken": ACCESS_TOKEN,
            "timeStamp":   timestamp,
            "signature":   self.__signature
        })

    def deep_convert_unicode(self, key, layer):
        """
        Хэрвээ 'image' эсвэл 'driverPic' талбарын bytes утга ирвэл
        өөрийн SOAP хүсэлтийн өмнө base64-р хөрвүүлэх буюу encode хийхэд ашиглана.
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
        Хэрвээ nested bytes объект ирэх тохиолдолд dict болгож хөрвүүлэх.
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
        WS100401_getVehicleInfo үйлдлийг дуудаж тээврийн мэдээллийг авна.

        plate_number: Машины улсын дугаар (жишээ: "5705УКМ")
        ------------------------------------------------------------------
        Серверийн өгөгдсөн загварын дагуу 'auth' блокоор сертификатын
        SHA1 fingerprint, иргэний регистрийн дугаар, signature-г дамжуулна.
        ------------------------------------------------------------------
        Хариу дахь resultCode:
          0 = Амжилттай
          3 = Хүчингүй хандалт (invalid access)
          Бусад код = Алдаа (баримт бичгээр шалгана)
        """

        # 4) auth блокоор шаардлагатай талбаруудыг дамжуулна
        #    - certFingerprint: openssl-ээр авсан SHA1 fingerprint (колонуусгүй, бүх үсэг их эсвэл их/жижиг бүгд зөвшөөрөгддөг байж болно)
        #    - regnum: Таны иргэний регистрын дугаар
        #    - signature: XypSign-аар ACCESS_TOKEN+timestamp дээр гарын үсэг хийсэн утга
        auth_block = {
            "citizen": {
                "authType":        0,  # 0 = сертификат (digital certificate) ашиглах
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

        # Debug хэвлэх (үгүйсгэхгүй бол устгана)
        print("---- AUTH BLOCK ----")
        print(auth_block)
        print("--------------------")

        # 5) Request параметрүүд
        params = {
            "auth":             auth_block,
            "cabinNumber":      None,
            "certificatNumber": None,
            "plateNumber":      plate_number,
            "regnum":           REGNUM
        }

        # 6) WS100401_getVehicleInfo үйлдлийг дуудаж, хариу авах
        try:
            response = self.client.service.WS100401_getVehicleInfo(params)
            return response
        except Exception as e:
            print(f"WS100401_getVehicleInfo алдаа: {e}")
            return None


if __name__ == "__main__":
    # 7) Программыг сорилтдоо ажиллуулах жишээ
    wsdl_url = "https://xyp.gov.mn/transport-1.3.0/ws?WSDL"
    timestamp = str(int(time.time() * 1000))

    svc = Service(wsdl_url, timestamp)
    result = svc.get_vehicle_info("5705УКМ")
    print("Хариу:", result)
