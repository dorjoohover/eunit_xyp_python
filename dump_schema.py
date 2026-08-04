# -*- coding: utf-8 -*-
"""
WS100401_getVehicleInfo (болон бусад vehicle service) дуудлагын жинхэнэ
WSDL/XSD бүтцийг хэвлэж, аль талбар "заавал" (required) болохыг харуулна.

ХУР-ын дэмжлэгийн баг resultCode 3-ыг "заавал байх шаардлагатай утгыг
хоосон явуулсан" гэж тайлбарласан хэдий ч бид олон янзын хослолоор
(auth блоктой/блокгүй, client TLS сертификаттай/сертификатгүй) тест хийхэд
яг ижил алдаа давтагдсаар байгаа тул схемийг өөрийг нь харж, аль талбар
яг заавал (minOccurs=1, nillable=false гэх мэт) болохыг нүдээрээ шалгах
шаардлагатай боллоо.

Ажиллуулах (энэ серверээс, учир нь зөвхөн энд xyp.gov.mn руу хандах
боломжтой):
    python3 dump_schema.py

Гаралтыг бүхэлд нь хуулж илгээнэ үү.
"""
import urllib3
from requests import Session
from zeep import Client
from zeep.transports import Transport

urllib3.disable_warnings()

WSDL = "https://xyp.gov.mn/transport-1.3.0/ws?WSDL"

session = Session()
session.verify = False
transport = Transport(session=session)
client = Client(WSDL, transport=transport)

print("=" * 80)
print("OPERATION SIGNATURE: WS100401_getVehicleInfo")
print("=" * 80)
print(client.service.WS100401_getVehicleInfo)

print()
print("=" * 80)
print("ALL TYPES CONTAINING 'vehicle' OR 'auth' OR 'Auth' IN NAME")
print("=" * 80)

# zeep-ийн бүх бүртгэгдсэн төрлүүдийг гүйж, нэрэнд нь vehicle/auth орсныг
# бүгдийг нь дэлгэрэнгүй хэвлэнэ (аль хувилбар дээр ч ажиллана).
seen = set()
for schema in client.wsdl.types.schemas.values():
    for type_name, type_obj in list(schema._types.items()):
        name = str(type_name)
        if name in seen:
            continue
        if "vehicle" in name.lower() or "auth" in name.lower():
            seen.add(name)
            print(f"--- {name} ---")
            try:
                print(type_obj.signature())
            except Exception as e:
                print(f"(signature() алдаа: {e})")
            print()
