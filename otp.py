# -- coding: utf-8 --
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
from env import REGNUM, CERT_PATH, KEY_PATH, ACCESS_TOKEN
class XypSign:
    def __init__(self, KeyPath):
        self.KeyPath = KeyPath 

    def __GetPrivKey(self):
        with open(self.KeyPath, "rb") as keyfile:
            return RSA.importKey(keyfile.read())

    def __toBeSigned(self, accessToken):
        return {
            'accessToken': accessToken,
            'timeStamp': self.__timestamp(),
        }

    def __buildParam(self, toBeSigned):        
        return toBeSigned['accessToken'] + '.' + toBeSigned['timeStamp']

    def sign(self, accessToken):
        toBeSigned = self.__toBeSigned(accessToken)
        digest = SHA256.new()
        digest.update(self.__buildParam(toBeSigned).encode('utf8'))
        pkey = self.__GetPrivKey()
        dd = b64encode(PKCS1_v1_5.new(pkey).sign(digest))
        return toBeSigned, dd.decode('utf-8')

    def __timestamp(self):
        return str(int(time.time()))

class Service:
    def __init__(self, wsdl, accesstoken, pkey_path=None, ca_cert_path=None):
        self.__accessToken = accesstoken
        self.__toBeSigned, self.__signature = XypSign(pkey_path).sign(self.__accessToken)
        urllib3.disable_warnings()
        session = Session()
        if ca_cert_path:
            session.verify = ca_cert_path   # SSL CA cert path (жишээ нь: 'ca_cert.pem')
        else:
            session.verify = False          # WARNING: Зөвхөн test орчинд хэрэглэ!
        transport = Transport(session=session)
        self.client = Client(wsdl, transport=transport)
        self.client.transport.session.headers.update({
            'accessToken': self.__accessToken,
            'timeStamp': self.__toBeSigned['timeStamp'],
            'signature': self.__signature
        })

    def dump(self, operation, params=None):
        try:
            if params:
                response = self.client.service[operation](params)
                print(response)
                return response
            else:
                response = self.client.service[operation]()
                print(response)
                return response
        except Exception as e:
            print(operation, str(e))
            return None

# -------------------------------
# Доор test/run хэсэг
if __name__ == "__main__":
    wsdlurl = 'https://xyp.gov.mn/property-1.3.0/ws?WSDL'  # жишээ wsdl
    accesstoken =   ACCESS_TOKEN     # test token (жинхэнэ бол өөрийн токен)
    keypath = KEY_PATH                              # Приват key зам (PEM)
    # ca_cert_path = 'ca_cert.pem'                          # Хэрвээ SSL CA cert шаардвал path оруул

    servicename = 'WS100202_getPropertyList'                # дуудмаар байгаа service-ийн нэр
    params = {'regnum': REGNUM}                       # service-ийн parameter

    # ca_cert_path өгч болох ба тест орчинд False-р болно
    citizen = Service(wsdlurl, accesstoken, keypath)  #, ca_cert_path) 
    citizen.dump(servicename, params)
