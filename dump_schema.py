# -*- coding: utf-8 -*-
"""
WS100401_getVehicleInfo дуудлагад ашиглагдах "vehicleRequestData" төрлийн
бодит XSD бүтцийг (талбар бүр, түүний min_occurs/nillable-ийг оруулаад)
рекурсивоор хэвлэж, аль талбар үнэхээр "заавал" болохыг харуулна.

Ажиллуулах (зөвхөн xyp.gov.mn руу network хандалттай серверээс):
    source venv/bin/activate
    python3 dump_schema.py

Гаралтыг бүхэлд нь хуулж илгээнэ үү.
"""
import urllib3
from requests import Session
from zeep import Client
from zeep.transports import Transport

urllib3.disable_warnings()

WSDL = "https://xyp.gov.mn/transport-1.3.0/ws?WSDL"
NS = "http://transport.xyp.gov.mn/"

session = Session()
session.verify = False
transport = Transport(session=session)
client = Client(WSDL, transport=transport)


def describe(type_obj, indent=0, seen=None):
    if seen is None:
        seen = set()
    pad = "  " * indent
    elements = getattr(type_obj, "elements", None)
    if not elements:
        return
    for name, element in elements:
        try:
            min_occurs = element.min_occurs
            max_occurs = element.max_occurs
            nillable = getattr(element, "nillable", None)
        except Exception as e:
            print(f"{pad}- {name}: <inspect error: {e}>")
            continue
        etype = element.type
        required_mark = "REQUIRED" if (min_occurs or 0) >= 1 else "optional"
        print(
            f"{pad}- {name}: type={etype} min_occurs={min_occurs} "
            f"max_occurs={max_occurs} nillable={nillable} -> {required_mark}"
        )
        key = str(getattr(etype, "qname", etype))
        if key not in seen and hasattr(etype, "elements") and etype.elements:
            seen.add(key)
            describe(etype, indent + 1, seen)


print("=" * 80)
print("vehicleRequestData бүтэц (талбар бүрийн required эсэхийг харуулна)")
print("=" * 80)
try:
    req_type = client.get_type(f"{{{NS}}}vehicleRequestData")
    describe(req_type)
except Exception as e:
    print(f"get_type алдаа: {e}")

print()
print("=" * 80)
print("WSDL бүтэн dump (нэмэлт лавлагаа)")
print("=" * 80)
print(client.wsdl.dump())
