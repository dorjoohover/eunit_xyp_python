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
from requests import Session
from requests.exceptions import ConnectionError as ReqConnectionError
from zeep import Client
from zeep.transports import Transport
from zeep.helpers import serialize_object
from zeep.exceptions import Fault, TransportError
from Crypto.Hash import SHA256
from Crypto.Signature import PKCS1_v1_5
from Crypto.PublicKey import RSA

from env import ACCESS_TOKEN, KEY_PATH

urllib3.disable_warnings()

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("xyp-server")

# zeep-ийн явуулж/хүлээж авч буй бодит SOAP XML-ийг бүхэлд нь харуулна.
logging.getLogger("zeep.transports").setLevel(logging.DEBUG)
logging.getLogger("zeep.wsdl.bindings.soap").setLevel(logging.DEBUG)


def mask_token(token):
    """ACCESS_TOKEN-ийг ХУР-ын өөрийнх нь хэвшмэл маягаар ([95b3***563c])
    log-д бүрэн ил гаргалгүй хэсэгчлэн харуулна."""
    if not token or len(token) <= 8:
        return "****"
    return f"{token[:4]}{'*' * (len(token) - 8)}{token[-4:]}"


VEHICLE_WSDL = "https://xyp.gov.mn/transport-1.3.0/ws?WSDL"


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

    def __init__(self, wsdl, access_token, key_path):
        logger.debug("XypService: WSDL=%s key_path=%s", wsdl, key_path)
        to_be_signed, signature = XypSign(key_path).sign(access_token)
        session = Session()
        session.verify = False
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


app = Flask(__name__)


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
    logger.debug(
        "/vehicle: num=%s (len=%d) ACCESS_TOKEN=%s KEY_PATH=%s",
        num, len(num), mask_token(ACCESS_TOKEN), KEY_PATH,
    )

    if not ACCESS_TOKEN or not KEY_PATH:
        logger.error("/vehicle: ACCESS_TOKEN эсвэл KEY_PATH тохируулагдаагүй байна")
        return jsonify({"error": "ACCESS_TOKEN or KEY_PATH is missing"}), 500

    params = {
        "auth": None,
        "cabinNumber": None,
        "certificatNumber": None,
        "regnum": None,
    }
    if len(num) <= 7:
        params["plateNumber"] = num
    else:
        params["certificateNumber"] = num

    logger.info("/vehicle: SOAP руу явуулах params=%s", params)

    try:
        service = XypService(VEHICLE_WSDL, ACCESS_TOKEN, KEY_PATH)
        res = service.call("WS100401_getVehicleInfo", params)
        res_dict = serialize_object(res)
        logger.info("/vehicle: SOAP-аас ирсэн бүтэн хариу=%s", res_dict)

        result_code = None
        if isinstance(res_dict, dict):
            result_code = res_dict.get("resultCode")
        if result_code not in (None, 0, "0"):
            logger.warning(
                "/vehicle: resultCode=%s message=%s — илгээсэн params=%s",
                result_code,
                res_dict.get("resultMessage") if isinstance(res_dict, dict) else None,
                params,
            )

        return jsonify({"vehicle": res_dict}), 200

    except Fault as e:
        code = getattr(e, "code", None) or getattr(e, "actor", None)
        detail = getattr(e, "detail", None)
        logger.exception(
            "/vehicle: SOAP Fault code=%s message=%s detail=%s params=%s",
            code, e.message, detail, params,
        )
        return jsonify({"error": str(e)}), 500

    except (TransportError, ReqConnectionError) as e:
        logger.exception("/vehicle: Transport error calling xyp.gov.mn: %s", str(e))
        return jsonify({"error": str(e)}), 500

    except Exception as e:
        logger.exception("/vehicle: Unhandled error, params=%s", params)
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    # dev/test-д зориулсан; prod дээр gunicorn ашиглана (README-г үз)
    app.run(host="0.0.0.0", port=8088)
