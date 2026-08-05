# -*- coding: utf-8 -*-
"""
ХУР (xyp.gov.mn) руу SOAP дуудалт хийдэг цорын ганц, цэвэр Flask wrapper.

Зөвхөн эдгээр 3 файл дээр тулгуурална: app.py (энэ файл), env.py
(тохиргоо), SimpleRequest.py (ХУР-ын өөрийнх нь жишээ кодтой ижил,
командын мөрөөс шалгах зориулалттай туслах скрипт). Бусад хуучин
файлууд (server.py, XypClient.py, XypSign.py, client.py гэх мэт)
цаашид ашиглагдахгүй.

Ажиллуулах (dev):
    python3 app.py

Ажиллуулах (prod, systemd-ээс дуудна) — АНХААР: systemd unit-ийн
ExecStart мөрийг "server:app"-аас "app:app" болгож солих ёстой:
    gunicorn -w 2 -b 0.0.0.0:8088 app:app
"""
import logging
import os
import time
from base64 import b64encode

import urllib3
from flask import Flask, request, jsonify, abort
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
logger = logging.getLogger("xyp-app")

# zeep-ийн явуулж/хүлээж авч буй бодит SOAP XML-ийг бүхэлд нь харуулна.
logging.getLogger("zeep.transports").setLevel(logging.DEBUG)
logging.getLogger("zeep.wsdl.bindings.soap").setLevel(logging.DEBUG)


def mask_token(token):
    """ACCESS_TOKEN-ийг ХУР-ын өөрийнх нь хэвшмэл маягаар ([95b3***563c])
    log-д бүрэн ил гаргалгүй хэсэгчлэн харуулна."""
    if not token or len(token) <= 8:
        return "****"
    return f"{token[:4]}{'*' * (len(token) - 8)}{token[-4:]}"


DEFAULT_SERVICE_GROUP = "transport"
DEFAULT_VERSION = "1.3.0"
SUPPORTED_SERVICE_GROUPS = {"property", "transport"}


def resolve_existing_path(path):
    if not path:
        return path

    local_candidate = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        os.path.basename(path),
    )

    for candidate in (path, local_candidate):
        if os.path.exists(candidate):
            return candidate

    return path


def build_wsdl_url(service_group, version):
    normalized_group = str(service_group or DEFAULT_SERVICE_GROUP).strip().lower()
    normalized_version = str(version or DEFAULT_VERSION).strip()

    if normalized_group not in SUPPORTED_SERVICE_GROUPS:
        raise ValueError(
            f"Unsupported serviceGroup={normalized_group!r}. "
            f"Supported values: {sorted(SUPPORTED_SERVICE_GROUPS)}"
        )

    return f"https://xyp.gov.mn/{normalized_group}-{normalized_version}/ws?WSDL"


class XypSign:
    """SimpleRequest.py (= ХУР-ын өөрийнх нь жишээ код)-той ЯГ ИЖИЛ гарын
    үсэг зурах логик — зөвхөн лог нэмсэн."""

    def __init__(self, key_path):
        self.key_path = key_path

    def _priv_key(self):
        with open(self.key_path, "rb") as keyfile:
            return RSA.importKey(keyfile.read())

    def sign(self, access_token):
        to_be_signed = {
            "accessToken": access_token,
            "timeStamp": str(int(time.time())),
        }
        digest = SHA256.new()
        digest.update(
            (to_be_signed["accessToken"] + "." + to_be_signed["timeStamp"]).encode("utf8")
        )
        signature = b64encode(PKCS1_v1_5.new(self._priv_key()).sign(digest))
        logger.debug(
            "XypSign: accessToken=%s timeStamp=%s signature=%s",
            mask_token(access_token),
            to_be_signed["timeStamp"],
            signature.decode("ascii"),
        )
        return to_be_signed, signature


class XypService:
    def __init__(self, wsdl, access_token, cert_path, key_path):
        resolved_cert_path = resolve_existing_path(cert_path)
        resolved_key_path = resolve_existing_path(key_path)

        logger.debug(
            "XypService: WSDL=%s cert_path=%s key_path=%s",
            wsdl,
            resolved_cert_path,
            resolved_key_path,
        )

        to_be_signed, signature = XypSign(resolved_key_path).sign(access_token)

        session = Session()
        session.verify = False

        # ХУР-аас олгосон TLS client certificate + private key
        session.cert = (resolved_cert_path, resolved_key_path)

        transport = Transport(session=session)

        self.client = Client(wsdl, transport=transport)

        self.client.transport.session.headers.update({
            "accessToken": access_token,
            "timeStamp": to_be_signed["timeStamp"],

            # bytes биш string болгон явуулах нь найдвартай
            "signature": signature.decode("ascii"),
        })

        logger.debug(
            "XypService: HTTP headers=%s",
            {
                **self.client.transport.session.headers,
                "accessToken": mask_token(access_token),
                "signature": "***MASKED***",
            },
        )

    def call(self, operation, params=None):
        logger.debug(
            "XypService.call: operation=%s params=%s",
            operation,
            params,
        )

        if params is not None:
            result = self.client.service[operation](params)
        else:
            result = self.client.service[operation]()

        logger.debug("XypService.call: raw result=%r", result)
        return result


def classify_xyp_result(result_dict):
    """Map XYP result codes/messages to a more accurate HTTP status."""
    if not isinstance(result_dict, dict):
        return 502, "XYPMalformedResponse"

    result_code = result_dict.get("resultCode")
    result_message = str(result_dict.get("resultMessage") or "").lower()

    if result_code in (0, "0"):
        return 200, None

    if result_code in (1, "1"):
        return 404, "XYPNotFound"

    if result_code in (3, "3"):
        if "хүчингүй хандалт" in result_message:
            return 403, "XYPAccessDenied"
        return 400, "XYPInvalidRequest"

    return 502, "XYPUpstreamError"


def execute_xyp_call(wsdl, operation, params):
    service = XypService(
        wsdl,
        ACCESS_TOKEN,
        CERT_PATH,
        KEY_PATH,
    )

    result = service.call(operation, params)
    result_dict = serialize_object(result)

    logger.info("/xyp: SOAP-аас ирсэн хариу=%s", result_dict)

    http_status, error_type = classify_xyp_result(result_dict)
    response_body = {
        "wsdl": wsdl,
        "operation": operation,
        "result": result_dict,
    }

    if error_type:
        response_body["error"] = {
            "type": error_type,
            "resultCode": (
                result_dict.get("resultCode")
                if isinstance(result_dict, dict)
                else None
            ),
            "message": (
                result_dict.get("resultMessage")
                if isinstance(result_dict, dict)
                else "Malformed XYP response",
            ),
        }

        logger.warning(
            "/xyp: XYP non-success resultCode=%s errorType=%s httpStatus=%s",
            response_body["error"]["resultCode"],
            error_type,
            http_status,
        )

    return response_body, http_status


app = Flask(__name__)


@app.get("/health")
def health():
    return jsonify({"status": "ok"}), 200


@app.post("/xyp/call")
def xyp_call():
    logger.info("=== /xyp/call: шинэ хүсэлт ирлээ ===")

    body = request.get_json(silent=True) or {}
    logger.debug("/xyp/call: incoming body=%s", body)

    operation = str(body.get("operation") or "").strip()
    if not operation:
        return jsonify({"error": "operation талбар шаардлагатай"}), 400

    params = body.get("params")
    if params is not None and not isinstance(params, dict):
        return jsonify({"error": "params нь JSON object байх ёстой"}), 400

    try:
        wsdl = body.get("wsdl") or build_wsdl_url(
            body.get("serviceGroup"),
            body.get("version"),
        )
        response_body, http_status = execute_xyp_call(wsdl, operation, params)
        return jsonify(response_body), http_status

    except ValueError as exc:
        return jsonify({"error": str(exc), "type": "ValidationError"}), 400

    except Fault as exc:
        logger.exception("/xyp/call: SOAP Fault")
        return jsonify({
            "error": str(exc),
            "type": "SOAPFault",
        }), 502

    except (TransportError, ReqConnectionError) as exc:
        logger.exception("/xyp/call: Transport error")
        return jsonify({
            "error": str(exc),
            "type": "TransportError",
        }), 502

    except Exception as exc:
        logger.exception("/xyp/call: Unhandled error, body=%s", body)
        return jsonify({
            "error": str(exc),
            "type": type(exc).__name__,
        }), 500


@app.post("/vehicle")
def vehicle():
    logger.info("=== /vehicle: шинэ хүсэлт ирлээ ===")

    body = request.get_json(silent=True) or {}
    logger.debug("/vehicle: incoming body=%s", body)

    plate_number = str(
        body.get("plateNumber")
        or body.get("num")
        or ""
    ).strip().upper()

    cabin_number = str(
        body.get("cabinNumber")
        or ""
    ).strip()

    certificat_number = str(
        body.get("certificatNumber")
        or body.get("certificateNumber")
        or ""
    ).strip()

    if not plate_number and not cabin_number and not certificat_number:
        return jsonify({
            "error": (
                "plateNumber, num, cabinNumber, certificatNumber "
                "талбаруудын аль нэгийг оруулна уу"
            )
        }), 400

    params = {}
    if plate_number:
        params["plateNumber"] = plate_number

    if cabin_number:
        params["cabinNumber"] = cabin_number

    if certificat_number:
        params["certificatNumber"] = certificat_number

    if not params and REGNUM:
        params["regnum"] = REGNUM

    logger.info("/vehicle: SOAP руу явуулах params=%s", params)

    try:
        wsdl = body.get("wsdl") or build_wsdl_url(
            DEFAULT_SERVICE_GROUP,
            body.get("version"),
        )
        operation = str(body.get("operation") or "WS100401_getVehicleInfo").strip()
        response_body, http_status = execute_xyp_call(wsdl, operation, params)
        response_body["vehicle"] = response_body.pop("result")
        return jsonify(response_body), http_status

    except ValueError as exc:
        return jsonify({"error": str(exc), "type": "ValidationError"}), 400

    except Fault as exc:
        logger.exception("/vehicle: SOAP Fault")
        return jsonify({
            "error": str(exc),
            "type": "SOAPFault",
        }), 502

    except (TransportError, ReqConnectionError) as exc:
        logger.exception("/vehicle: Transport error")
        return jsonify({
            "error": str(exc),
            "type": "TransportError",
        }), 502

    except Exception as exc:
        logger.exception(
            "/vehicle: Unhandled error, params=%s",
            params,
        )
        return jsonify({
            "error": str(exc),
            "type": type(exc).__name__,
        }), 500
if __name__ == "__main__":
    # dev/test-д зориулсан; prod дээр gunicorn ашиглана (README-г үз)
    app.run(host="0.0.0.0", port=8088)
