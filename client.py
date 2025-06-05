# Service.py
# -*- coding: utf-8 -*-
from collections.abc import Mapping
import zeep, base64
from zeep import Client
from zeep.transports import Transport
from XypSign import XypSign
from requests import Session
import urllib3

# env.py-д дараах гурван хувьсагчийг тодорхойлсон байх ёстой:
# ACCESS_TOKEN = "..."
# CERT_PATH    = "/home/eunit/xyp/certificate.crt"
# KEY_PATH     = "/home/eunit/xyp/private.key"
from env import ACCESS_TOKEN, CERT_PATH, KEY_PATH

class Service:
    def __init__(self, wsdl_url: str, timestamp: str, pkey_path: str = None):
        # 1) ACCESS_TOKEN + timestamp дээр гарын үсэг үүсгэх
        self.__accessToken = ACCESS_TOKEN
        self.__toBeSigned, self.__signature = XypSign(pkey_path).sign(
            self.__accessToken, timestamp
        )

        # 2) requests.Session үүсгэн, SSL шалгалтыг хасах ба сертификат+ключийг тохируулах
        urllib3.disable_warnings()  # “InsecureRequestWarning” зэргийг хаах
        session = Session()
        session.verify = False      # SSL шалгалтыг түр хасна
        session.cert = (CERT_PATH, KEY_PATH)

        # Zeep-д зориулсан transport үүсгэж өгөх
        transport = zeep.Transport(session=session)

        # 3) Zeep client үүсгэж, HTTP-header-д accessToken, timeStamp, signature нэмэх
        self.client = zeep.Client(wsdl=wsdl_url, transport=transport)
        self.client.transport.session.headers.update({
            "accessToken": self.__accessToken,
            "timeStamp":   timestamp,
            "signature":   self.__signature
        })

    def deep_convert_unicode(self, key, layer):
        """
        Зарим параметр (жишээ нь зураг binary) байвал base64-р хөрвүүлэх
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
        Хэрвээ nested bytes байвал dict болгож хөрвүүлэх
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

    def dump(self, operation: str, params: dict = None):
        """
        operation: WS100401_getVehicleInfo гэх мэт operation нэр
        params:    (optional) operation-д дамжуулах dict хэлбэрийн параметрүүд
        """
        try:
            if params:
                print("Params:", params)
                response = self.client.service[operation](params)
            else:
                response = getattr(self.client.service, operation)()
            print("Response:", response)
            return response
        except Exception as e:
            print(f"Error in {operation}: {e}")
            return None
