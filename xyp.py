# -*- coding: utf-8 -*-

import time
import subprocess
from XypClient import Service    # таны Service класс
from env import ACCESS_TOKEN , CERT_PATH, KEY_PATH     # env.py дотор ACCESS_TOKEN, CERT_PATH, KEY_PATH, REGNUM орсон гэж таавалзав

# env.py
# ACCESS_TOKEN = "95b3************************563c"
# CERT_PATH    = "/home/eunit/xyp/certificate.crt"
# KEY_PATH     = "/home/eunit/xyp/private.key"
# REGNUM       = "ИХ97070415"

if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print("Usage: python call_ws.py <plate_or_cabin>")
        sys.exit(1)

    plate_or_cabin = sys.argv[1]
    timestamp = str(int(time.time()))

    # 1) Сертификатын SHA256 fingerprint-ийг OpenSSL-аар гаргаж авна
    cert_proc = subprocess.run([
        "openssl", "x509", "-noout", "-fingerprint", "-sha256", "-in", CERT_PATH
    ], capture_output=True)
    if cert_proc.returncode != 0:
        print("Fingerprint авахад алдаа:", cert_proc.stderr.decode())
        sys.exit(1)

    raw_fp = cert_proc.stdout.decode().strip()
    # raw_fp жишээ: "SHA256 Fingerprint=95:B3:A4:FF:…:56:3C"
    cert_fingerprint = raw_fp.split("=", 1)[1].replace(":", "").lower()
    # Яг “colon-гүй, бүгд жижиг үсгээр” хувилбар: "95b3a4ff…563c"

    # 2) ACCESS_TOKEN + timestamp дээр XypSign-ээр гарын үсэг (PKCS#7 base64) хийж авна
    from XypSign import XypSign
    _, signature_b64 = XypSign(KEY_PATH).sign(ACCESS_TOKEN, timestamp)
    # signature_b64 нь жишээ: "MIIGTjCCA/...hNj==" (урт тасралтгүй Base64 мөр)

    # 3) WS100401_getVehicleInfo-д шаардлагатай параметрүүдээ бэлтгэнэ
    params = {
        "request": {
            "auth": {
                # citizen талбар: WS schema-д шаардлагатай тул “dummy” өгүүлбэр
                "citizen": {
                    "authType": 1,          # dummy (OTP ашиглахгүй тул 1 ба otp=0 өгнө)
                    "certFingerprint": None,
                    "civilId": None,
                    "fingerprint": None,
                    "regnum": "ИХ97070415",
                    "signature": None
                },
                # operator талбар: яг энд сертификат+signature flow-оо оруулна
                "operator": {
                    "authType": 0,               # 0 = сертификат+signature ашиглана
                    "certFingerprint": cert_fingerprint,   # УРЬДЧИЛАН БОДСОН HEX
                    "civilId": None,
                    "fingerprint": None,
                    "regnum": None,
                    "signature": signature_b64   # УРЬДЧИЛАН БОДСОН BASE64(PKCS#7)
                }
            },
            "cabinNumber": None,
            "certificatNumber": None,
            "plateNumber": plate_or_cabin,
            "regnum": None
        },
        "requestId": None
    }

    # 4) Service-ээ үүсгээд дуудаж үзье
    svc = Service(
        wsdl="https://xyp.gov.mn/transport-1.3.0/ws?WSDL",
        timestamp=timestamp,
        pkey_path=KEY_PATH
    )
    response = svc.dump("WS100401_getVehicleInfo", params["request"])
    print("Эцсийн хариу:", response)
