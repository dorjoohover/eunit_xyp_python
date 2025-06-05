# soap_request.py
# -*- coding: utf-8 -*-

import time
import requests
from xml.etree import ElementTree as ET

from env import ACCESS_TOKEN, CERT_PATH, KEY_PATH, REGNUM
from XypSign import XypSign

# --------------------------------------------------------------------------------
# 1. WSDL ба SOAP endpoint тодорхойлно
# --------------------------------------------------------------------------------
wsdl_url      = "https://xyp.gov.mn/transport-1.3.0/ws?WSDL"
# WSDL-ийн "?WSDL"-г хаяад үнэхээр POST-илэх SOAP endpoint-ийг авна
soap_endpoint = wsdl_url.replace("?WSDL", "")

# Одоогийн timestamp (миллисекунд):
timestamp = str(int(time.time() * 1000))

# --------------------------------------------------------------------------------
# 2. ACCESS_TOKEN + timestamp дээр подпись үүсгэх (иргэн талын private key-ээр)
# --------------------------------------------------------------------------------
signer_citizen = XypSign(KEY_PATH)
_, sig_citizen = signer_citizen.sign(ACCESS_TOKEN, timestamp)

# Иргэний сертификатын SHA1 fingerprint-г дараах командыг өгөөд авсан гэж үзье:
#   openssl x509 -in /root/xyp/certificate.crt -noout -fingerprint -sha1
# Жишээ үр дүн: SHA1 Fingerprint=95:B3:A8:2A:5A:E6:4C:20:8C:FA:ED:0D:56:B7:56:3C
# Колонуусгүйгээр: "95B3A82A5AE64C208CFAED0D56B7563C"
citizen_fingerprint = "95B3A82A5AE64C208CFAED0D56B7563C"

# Машины улсын дугаар (жишээ):
plate_number = "5705УКМ"

# --------------------------------------------------------------------------------
# 3. SOAP Request XML үүсгэх (Operator блок байхгүй — зөвхөн citizen)
#    - Namespace-г яг WSDL-д заасан targetNamespace-ээр давхар тааруулна.
# --------------------------------------------------------------------------------

NS_SOAP = "http://schemas.xmlsoap.org/soap/envelope/"
NS_SRVC = "http://transport.xyp.gov.mn/"

# Envelope
envelope = ET.Element(
    "soapenv:Envelope",
    {
        "xmlns:soapenv": NS_SOAP,
        "xmlns:ser":     NS_SRVC
    }
)

# Header (хоосон)
ET.SubElement(envelope, "soapenv:Header")

# Body
body = ET.SubElement(envelope, "soapenv:Body")

# Үйлдэл (operation) элемент
operation = ET.SubElement(body, "ser:WS100401_getVehicleInfo")

# Request wrapper
request_el = ET.SubElement(operation, "request")

# auth блок (зөвхөн citizen тал)
auth_el = ET.SubElement(request_el, "auth")

citizen_el = ET.SubElement(auth_el, "citizen")
ET.SubElement(citizen_el, "authType").text        = "0"
ET.SubElement(citizen_el, "certFingerprint").text = citizen_fingerprint
ET.SubElement(citizen_el, "regnum").text          = REGNUM
ET.SubElement(citizen_el, "signature").text       = sig_citizen.decode() \
                                                  if isinstance(sig_citizen, bytes) \
                                                  else sig_citizen
ET.SubElement(citizen_el, "civilId").text         = ""
ET.SubElement(citizen_el, "fingerprint").text     = ""
ET.SubElement(citizen_el, "appAuthToken").text    = ""
ET.SubElement(citizen_el, "authAppName").text     = ""

# Бусад талбарууд
ET.SubElement(request_el, "cabinNumber").text      = ""
ET.SubElement(request_el, "certificatNumber").text = ""
ET.SubElement(request_el, "plateNumber").text      = plate_number
ET.SubElement(request_el, "regnum").text           = REGNUM

# --------------------------------------------------------------------------------
# 4. XML-ээ string болгож хөрвүүлэх
# --------------------------------------------------------------------------------
xml_str = ET.tostring(envelope, encoding="utf-8", method="xml").decode()

# --------------------------------------------------------------------------------
# 5. HTTP headers бэлдэх
#    - SOAPAction утга WSDL-д заасан яг утгатай байх ёстой.
# --------------------------------------------------------------------------------
headers = {
    "Content-Type": "text/xml; charset=utf-8",
    "SOAPAction":   "http://transport.xyp.gov.mn/WS100401_getVehicleInfo"
}

# --------------------------------------------------------------------------------
# 6. SOAP хүсэлтээ илгээх (cert=(CERT_PATH, KEY_PATH) → Иргэний сертификат + private key)
#    - verify=False нь curl -k (–insecure) мэт SSL шалгалтыг түр таслана.
# --------------------------------------------------------------------------------
response = requests.post(
    soap_endpoint,
    data=xml_str.encode("utf-8"),
    headers=headers,
    cert=(CERT_PATH, KEY_PATH),
    verify=False
)

# --------------------------------------------------------------------------------
# 7. Хариу шалгах
# --------------------------------------------------------------------------------
print("HTTP статус код:", response.status_code)
print("Response headers:", response.headers)
print("Response body:")
print(response.text)

# --------------------------------------------------------------------------------
# 8. (Хэрвээ шаардлагатай бол) XML-г парсинг хийж resultCode, resultMessage-ийг унших
# --------------------------------------------------------------------------------
try:
    root = ET.fromstring(response.content)
    ns = {"soapenv": NS_SOAP, "ser": NS_SRVC}
    body_elem = root.find("soapenv:Body", ns)
    resp_elem = body_elem.find("ser:WS100401_getVehicleInfoResponse", ns)
    return_el = resp_elem.find("return")
    result_code = return_el.find("resultCode").text
    result_msg  = return_el.find("resultMessage").text
    print("Parsed resultCode  :", result_code)
    print("Parsed resultMessage:", result_msg)
except Exception:
    pass
