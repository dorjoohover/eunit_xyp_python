# -*- coding: utf-8 -*-
"""
core/platform-с ирэх хүсэлтийг хүлээж аваад ХУР (xyp.gov.mn) руу SOAP
дуудалт хийж, машины мэдээллийг буцаадаг жижиг HTTP wrapper.

Ажиллуулах (dev):
    python3 server.py

Ажиллуулах (prod, systemd-ээс дуудна):
    gunicorn -w 2 -b 0.0.0.0:8088 server:app
"""
import time
from base64 import b64encode

import logging

import urllib3
from flask import Flask, request, jsonify, abort
from flask.json.provider import DefaultJSONProvider
from requests import Session
from requests.exceptions import ConnectionError as ReqConnectionError
from zeep import Client
from zeep.transports import Transport
from zeep.helpers import serialize_object
from zeep.exceptions import Fault, TransportError
from Crypto.Hash import SHA256
from Crypto.Signature import PKCS1_v1_5
from Crypto.PublicKey import RSA

from env import ACCESS_TOKEN, CERT_PATH, KEY_PATH, REGNUM

urllib3.disable_warnings()

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("xyp-server")

# zeep-ийн явуулж/хүлээж авч буй бодит SOAP XML-ийг бүхэлд нь харуулна
# (хүсэлт бүтэц алдаатай эсэхийг ХУР-ын тайлбараас үл хамааран өөрөө
# нүдээрээ шалгаж болохоор).
logging.getLogger("zeep.transports").setLevel(logging.DEBUG)
logging.getLogger("zeep.wsdl.bindings.soap").setLevel(logging.DEBUG)


def mask_token(token):
    """ACCESS_TOKEN-ийг ХУР-ын өөрийнх нь хэвшмэл маягаар ([95b3***563c])
    log-д бүрэн ил гаргалгүй хэсэгчлэн харуулна."""
    if not token or len(token) <= 8:
        return "****"
    return f"{token[:4]}{'*' * (len(token) - 8)}{token[-4:]}"

VEHICLE_WSDL = "https://xyp.gov.mn/transport-1.3.0/ws?WSDL"

# ХУР-ын мэдэгдэж буй resultCode-ууд (developer.xyp.gov.mn-ийн алдааны
# жагсаалт) — SOAP fault эсвэл response дотор ирэх тоон кодыг хүнд ойлгомжтой
# болгож харуулахад ашиглана.
XYP_ERROR_CODES = {
    "303": "FINGERPRINT_MATCH_TIMEOUT — хурууны хээ тулгах процесс хэт удаан байна",
    "304": "FINGERPRINT_MATCH_ERROR — хурууны хээ тулгах процессд алдаа гарлаа",
    "401": "SHOULD_RETURN_STATE_REGISTER — бүргэлийн газарт очиж бүртгэлээ шалгуулах шаардлагатай",
    "402": "NOT_OWNER — эзэмшигч биш болно",
    "501": "UNAUTHORIZED_ATTEMPT — зөвшөөрөгдөөгүй газарт хандалт",
    "601": "INVALID_SIGNATURE — тоон гарын үсгийн мэдээлэл зөрүүтэй байна",
    "602": "EXPIRED_CERTIFICATE — сертификатын хугацаа дууссан байна",
    "603": "INACTIVE_CERTIFICATE — хүчингүй сертификат",
}


def describe_xyp_code(code):
    code = str(code)
    return XYP_ERROR_CODES.get(code, "Тодорхойгүй ХУР код")


def json_safe(value):
    """zeep-ийн буцаадаг response дотор bytes (жишээ нь binary/масклагдсан
    талбарууд) байж болох тул, JSON-д хөрвүүлэхээс өмнө рекурсивоор
    string болгож ариутгана."""
    if isinstance(value, bytes):
        try:
            return value.decode("utf-8")
        except UnicodeDecodeError:
            return b64encode(value).decode("ascii")
    if isinstance(value, dict):
        return {k: json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(v) for v in value]
    return value


class XypSign:
    def __init__(self, key_path):
        self.key_path = key_path

    def _get_priv_key(self):
        with open(self.key_path, "rb") as keyfile:
            return RSA.importKey(keyfile.read())

    def _to_be_signed(self, access_token):
        return {
            "accessToken": access_token,
            "timeStamp": str(int(time.time())),
        }

    def _build_param(self, to_be_signed):
        return to_be_signed["accessToken"] + "." + to_be_signed["timeStamp"]

    def sign(self, access_token):
        to_be_signed = self._to_be_signed(access_token)
        digest = SHA256.new()
        digest.update(self._build_param(to_be_signed).encode("utf8"))
        pkey = self._get_priv_key()
        signature = b64encode(PKCS1_v1_5.new(pkey).sign(digest))
        logger.debug(
            "XypSign: accessToken=%s timeStamp=%s signature=%s",
            mask_token(access_token),
            to_be_signed["timeStamp"],
            signature.decode("ascii"),
        )
        return to_be_signed, signature


class XypService:
    """Жинхэнэ SOAP client — импорт хийхэд шууд дуудалт хийхгүй,
    зөвхөн ашиглах үед л client үүсгэнэ (client.py-ийн импортын side-effect
    асуудлыг давтахгүйн тулд)."""

    def __init__(self, wsdl, access_token, key_path, cert_path=None):
        logger.debug(
            "XypService: WSDL=%s key_path=%s cert_path=%s", wsdl, key_path, cert_path,
        )
        to_be_signed, signature = XypSign(key_path).sign(access_token)
        session = Session()
        session.verify = False
        if cert_path:
            # BUG FIX: ХУР-ын жишээ клиент (client.py, DigitalSignatureApprove.py-
            # той адил гарын үсэг) `session.cert = (CERT_PATH, KEY_PATH)`-ээр
            # mutual TLS клиент сертификат дамжуулдаг байсан бол манай server.py
            # энэ хэсгийг огт хийдэггүй байсан — зөвхөн accessToken/signature-ийн
            # header-ийг л явуулдаг байв. ХУР-ын дэмжлэгийн хариунд resultCode 3
            # "заавал байх шаардлагатай утгыг хоосон явуулсан" гэснийг үзвэл, энэ
            # client-сертификат нь тухайн токентой холбоотой шаардлагатай мэдээлэл
            # байж болзошгүй тул сэргээж нэмлээ (certificate.crt/mykey.key нь
            # тухайн CN=6910033_195 гэдгээрээ яг энэ токен/байгууллагад олгогдсон
            # гэдгийг баталгаажуулсан).
            session.cert = (cert_path, key_path)
        transport = Transport(session=session)

        self.client = Client(wsdl, transport=transport)
        self.client.transport.session.headers.update({
            "accessToken": access_token,
            "timeStamp": to_be_signed["timeStamp"],
            "signature": signature,
        })
        logger.debug(
            "XypService: HTTP headers=%s",
            {
                **self.client.transport.session.headers,
                "accessToken": mask_token(access_token),
            },
        )

    def call(self, operation, params=None):
        logger.debug("XypService.call: operation=%s params=%s", operation, params)
        if params:
            result = self.client.service[operation](params)
        else:
            result = self.client.service[operation]()
        logger.debug("XypService.call: raw result=%r", result)
        return result


class BytesSafeJSONProvider(DefaultJSONProvider):
    """Flask-ийн json.dumps ямар ч гүн/бүтэцтэй объект дотор bytes
    таарвал (жишээ нь zeep-ийн CompoundValue дотор binary талбар) crash
    хийхгүйгээр base64/utf-8 строк болгож хөрвүүлнэ — энэ бол
    json_safe()-ээс илүү найдвартай сүүлчийн хамгаалалт."""

    @staticmethod
    def default(obj):
        if isinstance(obj, bytes):
            try:
                return obj.decode("utf-8")
            except UnicodeDecodeError:
                return b64encode(obj).decode("ascii")
        return DefaultJSONProvider.default(obj)


app = Flask(__name__)
app.json = BytesSafeJSONProvider(app)


@app.get("/health")
def health():
    return jsonify({"status": "ok"}), 200


@app.post("/vehicle")
def vehicle():
    logger.info("=== /vehicle: шинэ хүсэлт ирлээ ===")
    body = request.get_json(silent=True)
    logger.debug("/vehicle: incoming body=%s", body)

    if not body or not body.get("num"):
        logger.warning("/vehicle: `num` талбар дутуу — body=%s", body)
        abort(400, description="Missing `num` field")

    num = str(body["num"])
    # OTP flow ашиглаж байгаа бол дуудагч талаас (core/platform) дамжуулна;
    # fingerprint flow-д certFingerprint/signature шаардлагатай (одоогоор
    # дэмжигдээгүй, ESIGN client шаарддаг тул headless серверт тохиромжгүй).
    otp_code = body.get("otp")

    logger.debug(
        "/vehicle: num=%s (len=%d) otp=%s ACCESS_TOKEN=%s KEY_PATH=%s CERT_PATH=%s REGNUM=%s",
        num, len(num), bool(otp_code), mask_token(ACCESS_TOKEN), KEY_PATH, CERT_PATH, REGNUM,
    )

    if not ACCESS_TOKEN or not KEY_PATH:
        logger.error("/vehicle: ACCESS_TOKEN эсвэл KEY_PATH тохируулагдаагүй байна")
        return jsonify({"error": "ACCESS_TOKEN or KEY_PATH is missing"}), 500

    # BUG FIX: ХУР-аас өгсөн жишээ клиент код (Service.dump) `auth` блокийг
    # ОГТ бичдэггүй — зөвхөн `regnum` (болон хэрэгцээт бол plateNumber/
    # certificatNumber) дамжуулаад л дуудаж байгаа. Бид өмнө нь `auth.citizen.
    # authType`-г гараар 0 (= хурууны хээ баталгаажуулалт) болгож бичсэн нь,
    # ХУР талын тохиргоонд citizen/operator аль аль нь authentication
    # шаардахгүй ("Үгүй") гэж баталгаажсан хэдий ч бид өөрсдөө headless
    # серверээс биет хурууны хээ өгөх боломжгүй тул үргэлж "*** NO ACCESS ***"
    # → resultCode 3 (хүчингүй хандалт) болж татгалздаг байсныг тайлбарлаж
    # байна. Одоо: OTP код өгөгдсөн үед л (жинхэнэ OTP урсгал хэрэгтэй үед)
    # auth блокийг authType=1-ээр илгээнэ; OTP өгөгдөөгүй бол ХУР-ын жишээтэй
    # адил auth блокийг огт оруулахгүй — zeep/WSDL-ийн өөрийнх нь default-аар
    # үлдээнэ.
    params = {
        "cabinNumber": None,
        "certificatNumber": None,
        "regnum": REGNUM,
    }
    if otp_code:
        params["auth"] = {
            "citizen": {
                "authType": 1,
                "regnum": REGNUM,  # env.py-д өгсөн РД
                "otp": otp_code,
            },
            "operator": {
                "authType": 0,
            },
        }
    if len(num) <= 7:
        params["plateNumber"] = num
    else:
        # WSDL-ийн жинхэнэ талбарын нэр "certificatNumber" (e дутуу) —
        # response-ийн "request" хэсэгт echo хийгдэж байгаагаас батлагдсан.
        # Өмнө нь "certificateNumber" (зөв бичилттэй) руу бичиж байсан нь
        # зэрэг оршдог "certificatNumber": None-той зөрчилдөж, урт дугаараар
        # (гэрчилгээний дугаар) хайхад шаардлагатай талбар хоосон үлддэг байсан.
        params["certificatNumber"] = num

    logger.info("/vehicle: SOAP руу явуулах params=%s", params)

    try:
        service = XypService(VEHICLE_WSDL, ACCESS_TOKEN, KEY_PATH, CERT_PATH)
        res = service.call("WS100401_getVehicleInfo", params)
        res_dict = json_safe(serialize_object(res))
        logger.info("/vehicle: SOAP-аас ирсэн бүтэн хариу=%s", res_dict)

        # ХУР зарим тохиолдолд амжилттай HTTP хариу дотор resultCode/
        # resultMessage-ээр алдаагаа буцаадаг тул шалгаж, байвал тодорхой
        # тайлбар нэмнэ.
        result_code = None
        if isinstance(res_dict, dict):
            result_code = res_dict.get("resultCode")

        payload = {"vehicle": res_dict}
        if result_code not in (None, 0, "0"):
            payload["xyp_error_code"] = str(result_code)
            payload["xyp_error_description"] = describe_xyp_code(result_code)
            logger.warning(
                "/vehicle: resultCode=%s (%s) — илгээсэн params=%s",
                result_code, describe_xyp_code(result_code), params,
            )
            return jsonify(payload), 502

        logger.info("/vehicle: амжилттай, resultCode=0")
        return jsonify(payload), 200

    except Fault as e:
        # SOAP fault — faultcode/faultstring/detail-ийг бүгдийг гаргаж өгнө
        code = getattr(e, "code", None) or getattr(e, "actor", None)
        detail = getattr(e, "detail", None)
        logger.exception(
            "/vehicle: SOAP Fault code=%s message=%s detail=%s params=%s",
            code, e.message, detail, params,
        )
        return jsonify({
            "error": "soap_fault",
            "message": str(e.message),
            "code": str(code) if code else None,
            "xyp_error_description": describe_xyp_code(code) if code else None,
            "detail": str(detail) if detail else None,
        }), 502

    except (TransportError, ReqConnectionError) as e:
        # Сүлжээ/DNS/TLS/HTTP-ийн түвшний алдаа (жишээ нь xyp.gov.mn
        # resolve хийгдэхгүй байх, эсвэл IP whitelist хараахан идэвхжээгүй)
        logger.exception("/vehicle: Transport error calling xyp.gov.mn: %s", str(e))
        return jsonify({
            "error": "transport_error",
            "message": str(e),
        }), 502

    except Exception as e:
        logger.exception("/vehicle: Unhandled error, params=%s", params)
        return jsonify({"error": "unhandled_error", "message": str(e)}), 500


if __name__ == "__main__":
    # dev/test-д зориулсан; prod дээр gunicorn ашиглана (README-г үз)
    app.run(host="0.0.0.0", port=8088)
