import time
from XypClient import Service
from env import REGNUM, KEY_PATH, CERT_PATH

def get_vehicle_info_with_otp(plate_or_cabin: str):
    params = {}
    if len(plate_or_cabin) <= 7:
        # 7 тэмдэгт эсвэл бага = улсын дугаар гэж үзнэ
        params["plateNumber"] = plate_or_cabin
    else:
        # урт>7 бол cabinNumber гэж үзнэ
        params["cabinNumber"] = plate_or_cabin

    # 2) Баталгаажуулалтын auth блокоо бүрдүүлнэ (OTP ашиглаж байгаа тул citizen талбар чухал)
    params["auth"] = {
        "citizen": {
            "authType": 0,      # OTP замаар баталгаажуулж байна
        },
        "operator": {
            "authType": 0       # операторын баталгаажуулалт шаардлагагүй
        }
    }
    timestamp = str(int(time.time()))
    client = Service(
        "https://xyp.gov.mn/transport-1.3.0/ws?WSDL",
        timestamp,
        pkey_path=KEY_PATH,
    )
    try:
        response = client.dump("WS100401_getVehicleInfo", params)
        print("Авто мэдээлэл амжилттай ирлээ:")
        print(response)
    except Exception as e:
        print("Авто мэдээлэл авах үед алдаа:", e)

if __name__ == "__main__":
    get_vehicle_info_with_otp('5705УКМ')   