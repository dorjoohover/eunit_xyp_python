# -*- coding: utf-8 -*-
from collections.abc import Mapping
import zeep, base64
from zeep import Client
from zeep.transports import Transport
from XypSign import XypSign
from requests import Session
import urllib3
import subprocess
from env import ACCESS_TOKEN, CERT_PATH, KEY_PATH, REGNUM

class Service():
    def __init__(self, wsdl, timestamp, pkey_path=None):
        # ACCESS_TOKEN, timestamp ашиглан XypSign-аас гарын үсэг авч байна
        self.__accessToken = ACCESS_TOKEN
        self.__toBeSigned, self.__signature = XypSign(pkey_path).sign(self.__accessToken, timestamp)

        # SSL сэрэмжлүүлгийг хааж, Zeep Client-ээ үүсгэнэ
        urllib3.disable_warnings()
        session = Session()
        session.verify = False
        transport = zeep.Transport(session=session)
        self.client = zeep.Client(wsdl, transport=transport)

        # HTTP Header-д ACCESS_TOKEN, timestamp, signature сэтгэлийг нэмнэ
        self.client.transport.session.headers.update({
            'accessToken': self.__accessToken,
            'timeStamp'  : timestamp,
            'signature'  : self.__signature
        })
        print("Сервер лүү явуулж буй HTTP Session:", self.client.transport.session)

    def deep_convert_unicode(self, key, layer):
        # ... (үгүүсгэсэн)
        to_ret = layer
        if isinstance(layer, bytes) and (key == 'image' or key == 'driverPic'):
            to_ret = base64.b64encode(layer)
        try:
            for key, value in to_ret.items():
                to_ret[key] = self.deep_convert_unicode(key, value)
        except AttributeError:
            pass
        return to_ret
        
    def deep_convert_dict(self, layer):
        # ... (үгүүсгэсэн)
        to_ret = layer
        if isinstance(layer, bytes):
            to_ret = dict(layer)
        try:
            for key, value in to_ret.items():
                to_ret[key] = self.deep_convert_dict(value)
        except AttributeError:
            pass
        return to_ret
    
    def dump(self, operation, params=None):
        try:
            if params:
                print("Дуудаж буй Operation:", self.client.service[operation])
                response = self.client.service[operation](params)
                print("Серверээс ирсэн raw хариу:", response)
                return response
            else:
                print(self.client.service[operation]())
        except Exception as e:
            print(operation, "– алдаа:", str(e))
            return None

def compute_cert_fingerprint(cert_path: str) -> str:
    """
    Сертификатын SHA256 fingerprint-ийг colon-гүй, бүх жижиг үсгээрх HEX утгаар буцаана.
    """
    proc = subprocess.run([
        "openssl", "x509", "-noout", "-fingerprint", "-sha256", "-in", cert_path
    ], capture_output=True)
    if proc.returncode != 0:
        raise RuntimeError("Fingerprint авахад алдаа: " + proc.stderr.decode())
    raw = proc.stdout.decode().strip()
    hex_fp = raw.split("=", 1)[1].replace(":", "").lower()
    return hex_fp

if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print("Usage: python xyp_cert_flow.py <plate_or_cabin>")
        sys.exit(1)

    plate_or_cabin = sys.argv[1]
    timestamp = str(int(time.time()))

    # 1) Сертификатын SHA256 fingerprint-ийг авна
    cert_fingerprint = compute_cert_fingerprint(CERT_PATH)
    print("certFingerprint (hex):", cert_fingerprint)

    # 2) ACCESS_TOKEN + timestamp дээрээс XypSign-ээр signature авна (хэт урт base64 мөр)
    #    Жишээ:
    signer = XypSign(KEY_PATH)
    to_be_signed, signature_b64 = signer.sign(ACCESS_TOKEN, timestamp)
    print("signature (base64 PKCS#7):", signature_b64)

    # 3) WS100401_getVehicleInfo-д зориулсан параметрууд
    params = {
        "plateNumber": plate_or_cabin,  # эсвэл cabinNumber хэрэглэж болно
        "auth": {
            "citizen": {
                "authType": 1,      # WS schema шаардлагад dummy утга өгөхөд
                "regnum": REGNUM,
                "otp": 0            # OTP flow хэрэглэхгүй тул 0
            },
            "operator": {
                "authType": 0,                 # сертификат+signature flow
                "certFingerprint": cert_fingerprint,
                "signature": signature_b64,
                "civilId": None,
                "fingerprint": None,
                "regnum": None
            }
        }
    }

    # 4) Service-ээ үүсгэн, dump дуудах
    svc = Service("https://xyp.gov.mn/transport-1.3.0/ws?WSDL", timestamp, KEY_PATH)
    resp = svc.dump("WS100401_getVehicleInfo", params)
    print("Хариу:", resp)
