import time 
import os
from client import Service
def read_item(val: str = ""):
    if not val:
        print({"code": 1})
        return
        # return JSONResponse({"code": 1}, status_code=status.HTTP_400_BAD_REQUEST)

    params = {}
    if len(val) <= 7:
        params.update({"plateNumber": val})
    else:
        params.update({"cabinNumber": val})

    try:
        key_path = os.getenv("KEY_PATH")
        print("KEY_PATH: ", key_path)
        if os.getenv("ENVIRONMENT") != "prod":
            return {
                "request": {
                    "auth": None,
                    "cabinNumber": None,
                    "certificatNumber": None,
                    "plateNumber": "1234УБА",
                    "regnum": None,
                },
                "requestId": "50990790-ca4f-4c5e-956f-6f085ddae619", "response": {
                    "archiveDate": None,
                    "archiveFirstNumber": "Ш001123c1dsadc122",
                    "archiveNumber": "Ш1020d123edc12",
                    "axleCount": 0,
                    "buildYear": 2012,
                    "cabinNumber": "ZVW413093916",
                    "capacity": 1797.0,
                    "certificateNumber": "4092859",
                    "className": "B",
                    "colorName": "Цайвар цэнхэр",
                    "countryName": "*** NO ACCESS ",
                    "fueltype": "Бензин - Цахилгаан",
                    "height": 1570.0,
                    "importDate": "2021-02-22T00:00:00+08:00",
                    "intent": " NO ACCESS ",
                    "length": 4610.0,
                    "manCount": 5,
                    "markName": "Toyota",
                    "mass": 1450.0,
                    "modelName": "Prius Alpha",
                    "motorNumber": None,
                    "ownerAddress": None,
                    "ownerCountry": " NO ACCESS ",
                    "ownerFirstname": " NO ACCESS ",
                    "ownerHandphone": " NO ACCESS ",
                    "ownerHomephone": " NO ACCESS ",
                    "ownerLastname": " NO ACCESS ",  "ownerRegnum": " NO ACCESS ",
                    "ownerType": " NO ACCESS ",
                    "ownerWorkphone": " NO ACCESS ***",
                    "plateNumber": "0892УБЛ",
                    "transmission": None,
                    "type": "Олон зориулалттай",
                    "typeId": 0,
                    "weight": 0.0,
                    "wheelPosition": "Баруун",
                    "width": 1770.0,
                },
                "resultCode": 0,
                "resultMessage": "амжилттай",
            }

        # if prod
        timestamp = str(int(time.time()))
        citizen = Service(
            "https://xyp.gov.mn/transport-1.3.0/ws?WSDL", timestamp, pkey_path=key_path)
        res = citizen.dump("WS100401_getVehicleInfo", params)
        return res
    except Exception as e:
        print(e)
        # return JSONResponse(
        #     {"code": 2, "message": str(e)},
        #     status_code=status.HTTP_400_BAD_REQUEST)
