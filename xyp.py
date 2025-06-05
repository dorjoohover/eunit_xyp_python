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
from env import (
    ACCESS_TOKEN,
    CERT_PATH, KEY_PATH, REGNUM,
    OPERATOR_CERT_PATH, OPERATOR_KEY_PATH, OPERATOR_REGNUM
)

class Service:
    """
    ХУР Төрийн Мэдээлэл Солилцооны системтэй SOAP-р холбогдож
    тээврийн мэдээлэл авах зориулалттай класс.
    """

    def __init__(self, wsdl_url: str, timestamp: str):
        """
        wsdl_url:   WSDL эндпоинтын URL (жишээ:
                    "https://xyp.gov.mn/transport-1.3.0/ws?WSDL")
        timestamp:  milliseconds-тэй тэмдэгт (стрингээр),
                    жишээ: str(int(time.time() * 1000))
        """

        # 1) Иргэн ("citizen") ACCESS_TOKEN + timestamp дээр подпись үүсгэх
        signer_citizen = XypSign(KEY_PATH)
        to_be_signed_citizen, signature_citizen = signer_citizen.sign(ACCESS_TOKEN, timestamp)

        # 2) Оператор ("operator") ACCESS_TOKEN + timestamp дээр өөрийн private key-ээр подпись үүсгэх
        signer_operator = XypSign(OPERATOR_KEY_PATH)
        to_be_signed_operator, signature_operator = signer_operator.sign(ACCESS_TOKEN, timestamp)

        # Debug хэвлэх (шууд сорилтод харуулах зорилгоор; шаардлагагүй бол устгана)
        print("---- DEBUG ----")
        print("Citizen ToBeSigned:", to_be_signed_citizen)
        print("Citizen Signature:", signature_citizen)
        print("Operator ToBeSigned:", to_be_signed_operator)
        print("Operator Signature:", signature_operator)
        print("----------------")

        self.__sig_citizen  = signature_citizen
        self.__sig_operator = signature_operator

        # 3) requests.Session үүсгэж, SSL шалгалтыг түр хасах, сертификат+private key-ээ тохируулах
        #    - session.verify=False нь curl -k (–insecure)-тэй адил SSL шалгалтыг түр тасалж холбогдоно.
        #    - Хэрвээ серверийн SSL сертификатын EKU-г зассан бол session.verify=True болгож ашиглана.
        urllib3.disable_warnings()
        session = Session()
        session.verify = False

        # HTTP(S) холболтоо citizen сертификат ба key-ээр явуулна (хэрвээ операторын хил хязгааргүйгээр ижил холболт хийх шаардлагатай бол ингэж)
        # Хэрвээ citizen болон operator тус тусдаа өөр HTTPS холболт хийх шаардлагатай бол өөр Transport үүсгэж ашиглана.
        session.cert = (CERT_PATH, KEY_PATH)

        transport = Transport(session=session)

        # 4) Zeep Client үүсгэж, HTTP header-д accessToken, timeStamp, signature (сарвалжигчийн elf-order) нэмэх
        self.client = Client(wsdl=wsdl_url, transport=transport)
        self.client.transport.session.headers.update({
            "accessToken": ACCESS_TOKEN,
            "timeStamp":   timestamp,
            "signature":   signature_citizen  # Энд citizen-ийн signature байдаг тул төвшний header-д түүнийг дамжуулна
        })

    def deep_convert_unicode(self, key, layer):
        """
        Хэрвээ 'image' эсвэл 'driverPic' талбарын bytes утга ирвэл
        base64-р хөрвүүлэх үйлдэл.
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
        Хэрвээ nested bytes объект ирэх тохиолдолд dict болгож хөрвүүлэх үйлдэл.
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
        WS100401_getVehicleInfo үйлдэл рүү хүсэлт илгээж,
        тээврийн мэдээллийг буцааж авна.
        --------------------------------------------------------------------
        plate_number: Машины улсын дугаар (жишээ: "5705УКМ")
        resultCode:
          0 = Амжилттай
          3 = Хүчингүй хандалт (invalid access)
          Бусад = Баримт бичгээр шалгана.
        """

        # 5) auth блокоор citizen болон operator талын сертификатын сертификатын fingerprint, regnum, signature-г дамжуулна

        # 5.1. Citizen талын SHA1 сертификатын fingerprint-ийг доорх байдлаар тодорхойлсон гэж үзье:
        #     openssl x509 -in /root/xyp/certificate.crt -noout -fingerprint -sha1
        #     → SHA1 Fingerprint=95:B3:A8:2A:5A:E6:4C:20:8C:FA:ED:0D:56:B7:56:3C
        #     → Колонуусгүйгээр: "95B3A82A5AE64C208CFAED0D56B7563C"
        citizen_fingerprint = "95B3A82A5AE64C208CFAED0D56B7563C"

        # 5.2. Operator талын SHA1 сертификатын fingerprint-ийг доорх байдлаар тодорхойлсон:
        #     openssl x509 -in /root/xyp/operator_certificate.crt -noout -fingerprint -sha1
        #     → SHA1 Fingerprint=AB:CD:EF:12:34:56:78:90:12:34:56:78:90:AB:CD:EF:12:34:56:78
        #     → Колонуусгүйгээр: "ABCDEF12345678901234567890ABCDEF12345678"
        operator_fingerprint = "ABCDEF12345678901234567890ABCDEF12345678"

        auth_block = {
            "citizen": {
                "authType":        0,                 # 0 = сертификат (digital certificate)
                "certFingerprint": citizen_fingerprint,
                "regnum":          REGNUM,
                "signature":       self.__sig_citizen,
                "civilId":         None,
                "fingerprint":     b"*** NO ACCESS ***",
                "appAuthToken":    None,
                "authAppName":     None
            },
            "operator": {
                "authType":        0,                 # 0 = сертификат
                "certFingerprint": operator_fingerprint,
                "regnum":          OPERATOR_REGNUM,
                "signature":       self.__sig_operator,
                "civilId":         None,
                "fingerprint":     b"*** NO ACCESS ***",
                "appAuthToken":    None,
                "authAppName":     None
            }
        }

        # Debug хэвлэх (алагдаж байвал шалгахад хэрэг болно)
        print("---- AUTH BLOCK ----")
        print(auth_block)
        print("--------------------")

        # 6) Request параметрүүдийг бэлдэнэ
        params = {
            "auth":             auth_block,
            "cabinNumber":      None,
            "certificatNumber": None,
            "plateNumber":      plate_number,
            "regnum":           REGNUM
        }

        # 7) WS100401_getVehicleInfo үйлдлийг дуудаж, хариу авах
        try:
            response = self.client.service.WS100401_getVehicleInfo(params)
            return response
        except Exception as e:
            print(f"WS100401_getVehicleInfo алдаа: {e}")
            return None


if __name__ == "__main__":
    # Программыг ажиллуулах жишээ
    wsdl_url = "https://xyp.gov.mn/transport-1.3.0/ws?WSDL"
    timestamp = str(int(time.time() * 1000))

    svc = Service(wsdl_url, timestamp)
    result = svc.get_vehicle_info("5705УКМ")
    print("Хариу:", result)
