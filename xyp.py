# soap_request.py
# -*- coding: utf-8 -*-

import time
import requests
from xml.etree import ElementTree as ET

from env import (
    ACCESS_TOKEN,
    CERT_PATH, KEY_PATH, REGNUM
)
from XypSign import XypSign

# --------------------------------------------------------------------------------
# 1. Вариаблуудыг тодорхойлно
# --------------------------------------------------------------------------------
wsdl_url = "https://xyp.gov.mn/transport-1.3.0/ws?WSDL"
soap_endpoint = wsdl_url.replace("?WSDL", "")  # POST-илэх SOAP endpoint

# Одоогоор хэрэглэж буй timestamp (миллисекунд):
timestamp = str(int(time.time() * 1000))

# --------------------------------------------------------------------------------
# 2. ACCESS_TOKEN + timestamp дээр подпись (signature) үүсгэх
#    - Citizen талын private key -> XypSign
#    - Operator талын private key -> XypSign
# --------------------------------------------------------------------------------
signer_citizen = XypSign(KEY_PATH)
_, sig_citizen = signer_citizen.sign(ACCESS_TOKEN, timestamp)



# 시민 인증을 위한 SHA1 fingerprint (openssl x509 -in <path> -noout -fingerprint -sha1)
# Колонуусгүйгээр зурагласан утга:
citizen_fingerprint  = "95B3A82A5AE64C208CFAED0D56B7563C"
operator_fingerprint = "ABCDEF12345678901234567890ABCDEF12345678"

# Машины улсын дугаар (жишээ):
plate_number = "5705УКМ"

# --------------------------------------------------------------------------------
# 3. SOAP Request XML барих
# --------------------------------------------------------------------------------
envelope = ET.Element(
    "soapenv:Envelope",
    {
        "xmlns:soapenv": "http://schemas.xmlsoap.org/soap/envelope/",
        "xmlns:ser":    "http://service.transport.xyp.gov.mn/"
    }
)

# Header
header = ET.SubElement(envelope, "soapenv:Header")
# (Ямар ч header элемэнт оруулахгүй учир хоосон)

# Body
body = ET.SubElement(envelope, "soapenv:Body")

# Үйлдэл (operation)
operation = ET.SubElement(body, "ser:WS100401_getVehicleInfo")

# Энд WSDL-д тохирсон wrapper-n нэр заримдаа <arg0> эсвэл <request> болдог.
# Манай системд энэ жишээ нь <request> гэж нэртэй гэж үзье:
request_el = ET.SubElement(operation, "request")

# --- auth блокоор hometown / operator талын мэдээлэл дамжуулах ---
auth_el = ET.SubElement(request_el, "auth")

# Citizen тал
citizen_el = ET.SubElement(auth_el, "citizen")
ET.SubElement(citizen_el, "authType").text        = "0"
ET.SubElement(citizen_el, "certFingerprint").text = citizen_fingerprint
ET.SubElement(citizen_el, "regnum").text          = REGNUM
ET.SubElement(citizen_el, "signature").text       = sig_citizen.decode() if isinstance(sig_citizen, bytes) else sig_citizen
ET.SubElement(citizen_el, "civilId").text         = ""
ET.SubElement(citizen_el, "fingerprint").text     = ""  # сервер шаардлагагүй
ET.SubElement(citizen_el, "appAuthToken").text    = ""
ET.SubElement(citizen_el, "authAppName").text     = ""

# Operator тал
operator_el = ET.SubElement(auth_el, "operator")
ET.SubElement(operator_el, "authType").text        = "0"
ET.SubElement(operator_el, "certFingerprint").text = operator_fingerprint
ET.SubElement(operator_el, "regnum").text          = ""
ET.SubElement(operator_el, "signature").text       = sig_operator.decode() if isinstance(sig_operator, bytes) else sig_operator
ET.SubElement(operator_el, "civilId").text         = ""
ET.SubElement(operator_el, "fingerprint").text     = ""  # сервер шаардлагагүй
ET.SubElement(operator_el, "appAuthToken").text    = ""
ET.SubElement(operator_el, "authAppName").text     = ""

# --- request-ийн бусад талбарууд ---
ET.SubElement(request_el, "cabinNumber").text      = ""
ET.SubElement(request_el, "certificatNumber").text = ""
ET.SubElement(request_el, "plateNumber").text      = plate_number
ET.SubElement(request_el, "regnum").text           = REGNUM

# --------------------------------------------------------------------------------
# 4. XML-ээ string болгон хөрвүүлэх
# --------------------------------------------------------------------------------
xml_str = ET.tostring(
    envelope,
    encoding="utf-8",
    method="xml"
).decode()

# --------------------------------------------------------------------------------
# 5. HTTP headers бэлдэх
# --------------------------------------------------------------------------------
headers = {
    "Content-Type": "text/xml; charset=utf-8",
    # Зарим SOAP серверууд SOAPAction-г шаарддаг байж болно.
    # WSDL файлд <soap:operation soapAction="..."/> хэсэгт заасан утгыг яг тааруулж оруул.
    "SOAPAction": "http://service.transport.xyp.gov.mn/WS100401_getVehicleInfo"
}

# --------------------------------------------------------------------------------
# 6. requests.post ашиглан SOAP хүсэлтээ явуулах
# --------------------------------------------------------------------------------
response = requests.post(
    soap_endpoint,
    data=xml_str.encode("utf-8"),
    headers=headers,
    cert=(CERT_PATH, KEY_PATH),  # Клиент сертификат + private key
    verify=False                 # curl -k адил SSL шалгалтыг тасалж холбогдоно
)

# --------------------------------------------------------------------------------
# 7. Хариу шалгах
# --------------------------------------------------------------------------------
print("HTTP статус код:", response.status_code)
print("Response headers:", response.headers)
print("Response body:")
print(response.text)

# Хэрвээ статус 200 ба XML дүрсийг харвал parsing хийж болно:
# root = ET.fromstring(response.content)
# … Body → WS100401_getVehicleInfoResponse элемэнтээс resultCode, resultMessage авах ...
