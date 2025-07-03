# -- coding: utf-8 --
from collections.abc import Mapping
import zeep
import base64
from zeep import Client
from zeep.transports import Transport
from requests import Session
import urllib3
import time
from base64 import b64encode
from Crypto.Hash import SHA256
from Crypto.Signature import PKCS1_v1_5
from Crypto.PublicKey import RSA
from env import REGNUM, ACCESS_TOKEN, KEY_PATH


class XypSign:
    def __init__(self, KeyPath):
        self.KeyPath = KeyPath

    def __get_priv_key(self):
        with open(self.KeyPath, "rb") as keyfile:
            return RSA.importKey(keyfile.read())

    def __timestamp(self):
        return str(int(time.time()))

    def sign(self, accessToken):
        timestamp = self.__timestamp()
        to_be_signed = f"{accessToken}.{timestamp}"
        digest = SHA256.new()
        digest.update(to_be_signed.encode('utf8'))
        pkey = self.__get_priv_key()
        signature = b64encode(PKCS1_v1_5.new(pkey).sign(digest))
        return {'accessToken': accessToken, 'timeStamp': timestamp}, signature


class Service:
    def __init__(self, wsdl, accesstoken, pkey_path):
        self.__accessToken = accesstoken
        self.__toBeSigned, self.__signature = XypSign(pkey_path).sign(self.__accessToken)

        urllib3.disable_warnings()
        session = Session()
        session.verify = False
        transport = Transport(session=session)

        self.client = Client(wsdl, transport=transport)
        self.client.transport.session.headers.update({
            'accessToken': self.__accessToken,
            'timeStamp': self.__toBeSigned['timeStamp'],
            'signature': self.__signature.decode('utf-8')
        })

    def call(self, operation, params=None):
        try:
            if params:
                response = self.client.service[operation](params)
            else:
                response = self.client.service[operation]()
            print(response)
        except Exception as e:
            print(f"Error calling {operation}: {e}")


# ❗ REGNUM нь таны улсын бүртгэлийн дугаар (e.g., "УК12345678") байх ёстой.
params = {
    'plateNumber': "5705УКМ"
}

citizen = Service(
    "https://xyp.gov.mn/transport-1.3.0/ws?WSDL",  # Хэрэв 1.5.0 бол энэ линкийг ашиглана
    ACCESS_TOKEN,
    KEY_PATH
)

citizen.call("WS100401_getVehicleInfo", params)
