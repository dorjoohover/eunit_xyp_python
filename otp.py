# soap_otp_vehicle_client.py
# -*- coding: utf-8 -*-

import time
import requests
from xml.etree import ElementTree as ET

from env import ACCESS_TOKEN, CERT_PATH, KEY_PATH, REGNUM
from XypSign import XypSign

# --------------------------------------------------------------------------------
# 1. WSDL URL-ууд ба SOAP endpoint-ууд (домайн нэр зөвшөөрөгдсөн)
# --------------------------------------------------------------------------------
META_WSDL_URL         = "https://xyp.gov.mn/meta-1.5.0/ws?WSDL"
TRANSPORT_WSDL_URL    = "https://xyp.gov.mn/transport-1.3.0/ws?WSDL"
META_SOAP_ENDPOINT    = META_WSDL_URL.replace("?WSDL", "")
TRANSPORT_SOAP_ENDPOINT = TRANSPORT_WSDL_URL.replace("?WSDL", "")

# Namespace-үүд (WSDL-д заасан targetNamespace)
NS_SOAP   = "http://schemas.xmlsoap.org/soap/envelope/"
NS_META   = "http://meta.xyp.gov.mn/"
NS_TRANS  = "http://transport.xyp.gov.mn/"

# Машины улсын дугаар (жишээ)
PLATE_NUMBER = "5705УКМ"

# --------------------------------------------------------------------------------
# 2. Подпись үүсгэх функц
# --------------------------------------------------------------------------------
def generate_signature(pkey_path: str, access_token: str, timestamp: str) -> str:
    """
    XypSign ашиглан ACCESS_TOKEN + timestamp дээр SHA256withRSA подпись үүсгэж,
    base64-ээр буцаана.
    """
    signer = XypSign(pkey_path)
    _, signature = signer.sign(access_token, timestamp)
    return signature.decode() if isinstance(signature, bytes) else signature

# --------------------------------------------------------------------------------
# 3. WS100008_registerOTPRequest – SOAP хүсэлт илгээх (OTP авах)
# --------------------------------------------------------------------------------
def request_otp():
    """
    WS100008_registerOTPRequest үйлдлээр OTP (SMS) авах Soap хүсэлт илгээж,
    HTTP статус ба raw response XML-г буцаана.
    """
    # 3.1. timestamp ба подпись үүсгэх
    timestamp = str(int(time.time() * 1000))
    signature = generate_signature(KEY_PATH, ACCESS_TOKEN, timestamp)

    # 3.2. HTTP header-үүд
    headers = {
        "Content-Type": "text/xml; charset=utf-8",
        "SOAPAction":   f"{NS_META}WS100008_registerOTPRequest",
        "accessToken":  ACCESS_TOKEN,
        "timeStamp":    timestamp,
        "signature":    signature
    }

    # 3.3. SOAP Envelope үүсгэх
    envelope = ET.Element(
        "soapenv:Envelope",
        {
            "xmlns:soapenv": NS_SOAP,
            "xmlns:met":     NS_META
        }
    )
    ET.SubElement(envelope, "soapenv:Header")
    body = ET.SubElement(envelope, "soapenv:Body")

    # 3.4. Үйлдэл: <met:WS100008_registerOTPRequest>
    operation = ET.SubElement(body, "met:WS100008_registerOTPRequest")

    # 3.5. auth блокоор citizen талын мэдээлэл (OTP авах үед otp=0)
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
    ET.SubElement(citizen_el, "otp").text             = "0"

    # 3.6. Бусад талбарууд
    ET.SubElement(operation, "regnum").text       = REGNUM
    ET.SubElement(operation, "jsonWSList").text   = "[{\"ws\":\"WS100401_getVehicleInfo\"}]"
    ET.SubElement(operation, "isSms").text        = "1"
    ET.SubElement(operation, "isApp").text        = "0"
    ET.SubElement(operation, "isEmail").text      = "0"
    ET.SubElement(operation, "isKiosk").text      = "0"
    ET.SubElement(operation, "phoneNum").text     = ""

    # 3.7. XML-ээ string болгон хөрвүүлэх
    xml_str = ET.tostring(envelope, encoding="utf-8", method="xml").decode()

    # 3.8. HTTP POST хийж response авч буцаах
    try:
        response = requests.post(
            META_SOAP_ENDPOINT,
            data=xml_str.encode("utf-8"),
            headers=headers,
            cert=(CERT_PATH, KEY_PATH),
            verify=False
        )
    except requests.exceptions.RequestException as e:
        print("OTP авахад холболтын алдаа:", e)
        return None, None

    return response.status_code, response.text

# --------------------------------------------------------------------------------
# 4. WS100401_getVehicleInfo – SOAP хүсэлт илгээх (OTP ашиглан)
# --------------------------------------------------------------------------------
def get_vehicle_info_with_otp(otp_code: int):
    """
    WS100401_getVehicleInfo үйлдлээр OTP-оор машин мэдээлэл авах Soap хүсэлт илгээж,
    HTTP статус ба raw response XML-г буцаана.
    """
    # 4.1. timestamp ба подпись үүсгэх
    timestamp = str(int(time.time() * 1000))
    signature = generate_signature(KEY_PATH, ACCESS_TOKEN, timestamp)

    # 4.2. HTTP header-үүд
    headers = {
        "Content-Type": "text/xml; charset=utf-8",
        "SOAPAction":   f"{NS_TRANS}WS100401_getVehicleInfo",
        "accessToken":  ACCESS_TOKEN,
        "timeStamp":    timestamp,
        "signature":    signature
    }

    # 4.3. SOAP Envelope үүсгэх
    envelope = ET.Element(
        "soapenv:Envelope",
        {
            "xmlns:soapenv": NS_SOAP,
            "xmlns:ser":     NS_TRANS
        }
    )
    ET.SubElement(envelope, "soapenv:Header")
    body = ET.SubElement(envelope, "soapenv:Body")

    # 4.4. Үйлдэл: <ser:WS100401_getVehicleInfo>
    operation = ET.SubElement(body, "ser:WS100401_getVehicleInfo")

    # 4.5. auth блокоор citizen талын мэдээлэл (OTP-н код оруулна)
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

    # 4.6. Бусад талбарууд
    ET.SubElement(operation, "cabinNumber").text      = ""
    ET.SubElement(operation, "certificatNumber").text = ""
    ET.SubElement(operation, "plateNumber").text      = PLATE_NUMBER
    ET.SubElement(operation, "regnum").text           = REGNUM

    # 4.7. XML-ээ string болгон хөрвүүлэх
    xml_str = ET.tostring(envelope, encoding="utf-8", method="xml").decode()

    # 4.8. HTTP POST хийж response авч буцаах
    try:
        response = requests.post(
            TRANSPORT_SOAP_ENDPOINT,
            data=xml_str.encode("utf-8"),
            headers=headers,
            cert=(CERT_PATH, KEY_PATH),
            verify=False
        )
    except requests.exceptions.RequestException as e:
        print("Машин мэдээлэл авахад холболтын алдаа:", e)
        return None, None

    return response.status_code, response.text

# --------------------------------------------------------------------------------
# 5. Алдааны (SOAP Fault) болон стандарт хариуг илүү ойлгомжтойгоор шалгаж хэвлэх
# --------------------------------------------------------------------------------
def print_response(status_code: int, raw_xml: str, service_ns: str, operation_name: str):
    """
    HTTP статус болон raw XML-г хэвлээд,
    хэрвээ <soap:Fault> байвал faultcode, faultstring-г харуулна;
    эсвэл operation_nameResponse→return→resultCode, resultMessage-г уншина.
    """
    if status_code is None:
        print("Холболт хийж чадсангүй.")
        return

    print(f"HTTP статус код: {status_code}")
    print("Raw response XML:")
    print(raw_xml)
    print("-" * 70)

    try:
        root = ET.fromstring(raw_xml)
        ns = {"soapenv": NS_SOAP, "svc": service_ns}

        # 5.1. SOAP Fault шалгах
        fault_elem = root.find(".//soapenv:Fault", {"soapenv": NS_SOAP})
        if fault_elem is not None:
            faultcode   = fault_elem.find("faultcode").text if fault_elem.find("faultcode") is not None else ""
            faultstring = fault_elem.find("faultstring").text if fault_elem.find("faultstring") is not None else ""
            print("SOAP Fault илэрлээ:")
            print("  faultcode   =", faultcode)
            print("  faultstring =", faultstring)
            return

        # 5.2. Хэрвээ Fault үгүй бол стандарт хариу унших
        resp_elem = root.find(f".//svc:{operation_name}Response", ns)
        if resp_elem is not None:
            return_el = resp_elem.find("return")
            if return_el is not None:
                result_code = return_el.find("resultCode").text if return_el.find("resultCode") is not None else ""
                result_msg  = return_el.find("resultMessage").text if return_el.find("resultMessage") is not None else ""
                print("Parsed resultCode   :", result_code)
                print("Parsed resultMessage:", result_msg)
                return

        print(f"{operation_name}Response элемент олдсонгүй эсвэл return талбар дутуу байна.")
    except ET.ParseError as pe:
        print("XML парсинг хийхэд алдаа:", pe)

# --------------------------------------------------------------------------------
# 6. OTP авах, дараа нь User-ээс өгсөн OTP-н кодоор машин мэдээлэл авах
# --------------------------------------------------------------------------------
def main():
    # 6.1. OTP авах хүсэлт
    status_otp, resp_otp = request_otp()
    print_response(status_otp, resp_otp, NS_META, "WS100008_registerOTPRequest")

    # 6.2. Хэрвээ OTP хүсэлт амжилттай (HTTP 200) буцаасан бол хэрэглэгчээс код асуух
    if status_otp == 200:
        try:
            otp_code = int(input("Иргэнд ирсэн OTP кодыг оруулна уу: ").strip())
        except ValueError:
            print("OTP код зөвхөн цифр байх ёстой.")
            return

        # 6.3. OTP кодоор машин мэдээлэл авах хүсэлт илгээх
        status_vehicle, resp_vehicle = get_vehicle_info_with_otp(otp_code)
        print_response(status_vehicle, resp_vehicle, NS_TRANS, "WS100401_getVehicleInfo")
    else:
        print("OTP авахад амжилтгүй (HTTP статус код != 200).")

if __name__ == "__main__":
    main()
