# soap_otp_client.py
# -*- coding: utf-8 -*-

import time
import requests
from xml.etree import ElementTree as ET

from env import ACCESS_TOKEN, CERT_PATH, KEY_PATH, REGNUM
from XypSign import XypSign

# --------------------------------------------------------------------------------
# 1. Тохиргоо: WSDL URL-ууд болон namespaces
# --------------------------------------------------------------------------------
META_WSDL_URL          = "https://xyp.gov.mn/meta-1.5.0/ws?WSDL"
TRANSPORT_WSDL_URL     = "https://xyp.gov.mn/transport-1.3.0/ws?WSDL"
META_SOAP_ENDPOINT     = META_WSDL_URL.replace("?WSDL", "")
TRANSPORT_SOAP_ENDPOINT = TRANSPORT_WSDL_URL.replace("?WSDL", "")

NS_SOAP = "http://schemas.xmlsoap.org/soap/envelope/"
NS_META = "http://meta.xyp.gov.mn/"          # Meta service-ийн targetNamespace
NS_TRANS = "http://transport.xyp.gov.mn/"    # Transport service-ийн targetNamespace

# --------------------------------------------------------------------------------
# 2. Утгууд: Иргэний мэдээлэл ба хувьсагчид
# --------------------------------------------------------------------------------
# Иргэний сертификатын SHA1 fingerprint:
#   openssl x509 -in /root/xyp/certificate.crt -noout -fingerprint -sha1
#   → SHA1 Fingerprint=95:B3:A8:2A:5A:E6:4C:20:8C:FA:ED:0D:56:B7:56:3C
#   → Колонуусгүйгээр: "95B3A82A5AE64C208CFAED0D56B7563C"
CITIZEN_FINGERPRINT = "95B3A82A5AE64C208CFAED0D56B7563C"

# OTP авахад ашиглах JSON форматын WS жагсаалт:
#  WS100008_registerOTPRequest-д jsonWSList = "[{\"ws\":\"WS100401_getVehicleInfo\"}]"
WS_LIST_JSON = "[{\"ws\":\"WS100401_getVehicleInfo\"}]"

# Машины улсын дугаар (WS100401_getVehicleInfo-д ашиглана)
PLATE_NUMBER = "5705УКМ"

# --------------------------------------------------------------------------------
# 3. Хэрэглэгчийн подпись үүсгэх функцийг бичнэ
# --------------------------------------------------------------------------------
def generate_signature(pkey_path: str, access_token: str, timestamp: str) -> str:
    """
    XypSign ашиглан ACCESS_TOKEN + timestamp дээр подпись үүсгэнэ (base64).
    """
    signer = XypSign(pkey_path)
    _, signature = signer.sign(access_token, timestamp)
    # Хэрвээ байт массив буцсан бол .decode()
    return signature.decode() if isinstance(signature, bytes) else signature

# --------------------------------------------------------------------------------
# 4. WS100008_registerOTPRequest – SOAP хүсэлт илгээх
# --------------------------------------------------------------------------------
def request_otp():
    """
    WS100008_registerOTPRequest үйлдлээр OTP (SMS) илгээх.
    Хариу болон HTTP статус кодыг буцаана.
    """
    # 4.1. timestamp болон подпись үүсгэх
    timestamp = str(int(time.time() * 1000))
    signature = generate_signature(KEY_PATH, ACCESS_TOKEN, timestamp)

    # 4.2. HTTP header-д хавсаргах утгууд
    headers = {
        "Content-Type":  "text/xml; charset=utf-8",
        "SOAPAction":    "http://meta.xyp.gov.mn/WS100008_registerOTPRequest",
        "accessToken":   ACCESS_TOKEN,
        "timeStamp":     timestamp,
        "signature":     signature
    }

    # 4.3. SOAP XML бүтцийг ElementTree ашиглан үүсгэж байна
    envelope = ET.Element(
        "soapenv:Envelope",
        {
            "xmlns:soapenv": NS_SOAP,
            "xmlns:met":     NS_META
        }
    )
    ET.SubElement(envelope, "soapenv:Header")
    body = ET.SubElement(envelope, "soapenv:Body")

    # 4.4. Үйлдэл: <met:WS100008_registerOTPRequest>
    operation = ET.SubElement(body, "met:WS100008_registerOTPRequest")

    # 4.5. auth блокоор citizen талын мэдээлэл
    auth_el = ET.SubElement(operation, "auth")
    citizen_el = ET.SubElement(auth_el, "citizen")
    ET.SubElement(citizen_el, "authType").text        = "1"  # 1 = OTP ашиглана
    ET.SubElement(citizen_el, "certFingerprint").text = ""
    ET.SubElement(citizen_el, "regnum").text          = REGNUM
    ET.SubElement(citizen_el, "signature").text       = ""
    ET.SubElement(citizen_el, "civilId").text         = ""
    ET.SubElement(citizen_el, "fingerprint").text     = ""
    ET.SubElement(citizen_el, "appAuthToken").text    = ""
    ET.SubElement(citizen_el, "authAppName").text     = ""
    ET.SubElement(citizen_el, "otp").text             = "0"  # Өмнө хоосон

    # 4.6. Бусад талбарууд
    ET.SubElement(operation, "regnum").text       = REGNUM
    ET.SubElement(operation, "jsonWSList").text   = WS_LIST_JSON
    ET.SubElement(operation, "isSms").text        = "1"
    ET.SubElement(operation, "isApp").text        = "0"
    ET.SubElement(operation, "isEmail").text      = "0"
    ET.SubElement(operation, "isKiosk").text      = "0"
    ET.SubElement(operation, "phoneNum").text     = ""  # Хэрвээ утасны дугаар тусдаа шаардлагатай бол ерөнхий осгоно

    # 4.7. XML-ээ string болгон хөрвүүлэх
    xml_str = ET.tostring(envelope, encoding="utf-8", method="xml").decode()

    # 4.8. SOAP хүсэлтийг илгээж, хариуг буцаах
    response = requests.post(
        META_SOAP_ENDPOINT,
        data=xml_str.encode("utf-8"),
        headers=headers,
        cert=(CERT_PATH, KEY_PATH),
        verify=False
    )

    return response.status_code, response.text
plate_number = '5705УКМ'
# --------------------------------------------------------------------------------
# 5. WS100401_getVehicleInfo – SOAP хүсэлт илгээх (OTP ашиглан)
# --------------------------------------------------------------------------------
def get_vehicle_info_with_otp(otp_code: int):
    """
    WS100401_getVehicleInfo үйлдлээр OTP-тай хамт машин мэдээлэл авах.
    Хариу болон HTTP статус кодыг буцаана.
    """
    # 5.1. timestamp болон подпись (OTP-т неогор SIGNATURE байнга хоосон өгөгдсөн учир
    #      header-д ACCESS_TOKEN+timestamp подпись хийж илгээж байна)
    timestamp = str(int(time.time() * 1000))
    signature = generate_signature(KEY_PATH, ACCESS_TOKEN, timestamp)

    # 5.2. HTTP header-д хавсаргах утгууд
    headers = {
        "Content-Type":  "text/xml; charset=utf-8",
        "SOAPAction":    "http://transport.xyp.gov.mn/WS100401_getVehicleInfo",
        "accessToken":   ACCESS_TOKEN,
        "timeStamp":     timestamp,
        "signature":     signature
    }

    # 5.3. SOAP XML бүтцийг ElementTree ашиглан үүсгэх
    envelope = ET.Element(
        "soapenv:Envelope",
        {
            "xmlns:soapenv": NS_SOAP,
            "xmlns:ser":     NS_TRANS
        }
    )
    ET.SubElement(envelope, "soapenv:Header")
    body = ET.SubElement(envelope, "soapenv:Body")

    # 5.4. Үйлдэл: <ser:WS100401_getVehicleInfo>
    operation = ET.SubElement(body, "ser:WS100401_getVehicleInfo")

    # 5.5. auth блокоор citizen талын мэдээлэл (OTP ашиглагддаг)
    auth_el = ET.SubElement(operation, "auth")
    citizen_el = ET.SubElement(auth_el, "citizen")
    ET.SubElement(citizen_el, "authType").text        = "1"  # 1 = OTP ашиглана
    ET.SubElement(citizen_el, "certFingerprint").text = ""
    ET.SubElement(citizen_el, "regnum").text          = REGNUM
    ET.SubElement(citizen_el, "signature").text       = ""
    ET.SubElement(citizen_el, "civilId").text         = ""
    ET.SubElement(citizen_el, "fingerprint").text     = ""
    ET.SubElement(citizen_el, "otp").text             = str(otp_code)
    ET.SubElement(citizen_el, "appAuthToken").text    = ""
    ET.SubElement(citizen_el, "authAppName").text     = ""

    # 5.6. Бусад талбарууд
    ET.SubElement(operation, "cabinNumber").text      = ""
    ET.SubElement(operation, "certificatNumber").text = ""
    ET.SubElement(operation, "plateNumber").text      = plate_number
    ET.SubElement(operation, "regnum").text           = REGNUM

    # 5.7. XML-ээ string болгон хөрвүүлэх
    xml_str = ET.tostring(envelope, encoding="utf-8", method="xml").decode()

    # 5.8. SOAP хүсэлтийг илгээж, хариуг буцаах
    response = requests.post(
        TRANSPORT_SOAP_ENDPOINT,
        data=xml_str.encode("utf-8"),
        headers=headers,
        cert=(CERT_PATH, KEY_PATH),
        verify=False
    )

    return response.status_code, response.text

# --------------------------------------------------------------------------------
# 6. OTP авах үйлдлийг дуудах, дараа нь тэр OTP-оор машин мэдээлэл авах
# --------------------------------------------------------------------------------
def main():
    # 6.1. OTP авах хүсэлт илгээх
    status_code, resp_text = request_otp()
    print("OTP request HTTP status:", status_code)
    print("OTP request response:\n", resp_text)
    print("--------------------------------------------------")

    # 6.2. Иргэдэд ирсэн OTP кодыг асуух
    try:
        otp_code = int(input("Иргэнд ирсэн OTP кодыг оруулна уу: ").strip())
    except ValueError:
        print("OTP бүртгэхэд алдаа: зөвхөн цифр оруулна уу.")
        return

    # 6.3. OTP кодоор машин мэдээлэл авах хүсэлт илгээх
    status_code, resp_text = get_vehicle_info_with_otp(otp_code)
    print("GetVehicleInfo HTTP status:", status_code)
    print("GetVehicleInfo response:\n", resp_text)

if __name__ == "__main__":
    main()
