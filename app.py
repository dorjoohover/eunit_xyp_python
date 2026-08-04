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


TRANSPORT_WSDL = "https://xyp.gov.mn/transport-1.3.0/ws?WSDL"


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
        logger.debug(
            "XypService: WSDL=%s cert_path=%s key_path=%s",
            wsdl,
            cert_path,
            key_path,
        )

        to_be_signed, signature = XypSign(key_path).sign(access_token)

        session = Session()
        session.verify = False

        # ХУР-аас олгосон TLS client certificate + private key
        session.cert = (cert_path, key_path)

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

app = Flask(__name__)


@app.get("/health")
def health():
    return jsonify({"status": "ok"}), 200


@app.post("/vehicle")
def vehicle():
    logger.info("=== /vehicle: шинэ хүсэлт ирлээ ===")

    body = request.get_json(silent=True) or {}
    logger.debug("/vehicle: incoming body=%s", body)

    plate_number = str(body.get("plateNumber") or body.get("num") or "").strip()
    cabin_number = str(body.get("cabinNumber") or "").strip()
    certificate_number = str(
        body.get("certificatNumber")
        or body.get("certificateNumber")
        or ""
    ).strip()

    if not plate_number and not cabin_number and not certificate_number:
        return jsonify({
            "error": (
                "plateNumber, cabinNumber, certificatNumber "
                "талбаруудын аль нэгийг оруулна уу"
            )
        }), 400

    params = {}

    if plate_number:
        params["plateNumber"] = plate_number.strip().upper()

    if cabin_number:
        params["cabinNumber"] = cabin_number

    if certificate_number:
        params["certificatNumber"] = certificate_number

    logger.info("/vehicle: SOAP руу явуулах params=%s", params)

    try:
        service = XypService(
    TRANSPORT_WSDL,
    ACCESS_TOKEN,
    CERT_PATH,
    KEY_PATH,
)

        result = service.call(
            "WS100401_getVehicleInfo",
            params
        )

        result_dict = serialize_object(result)

        logger.info(
            "/vehicle: SOAP-аас ирсэн хариу=%s",
            result_dict
        )

        return jsonify({
            "vehicle": result_dict
        }), 200

    except Fault as exc:
        logger.exception("/vehicle: SOAP Fault")
        return jsonify({
            "error": str(exc),
            "type": "SOAPFault"
        }), 502

    except (TransportError, ReqConnectionError) as exc:
        logger.exception("/vehicle: Transport error")
        return jsonify({
            "error": str(exc),
            "type": "TransportError"
        }), 502

    except Exception as exc:
        logger.exception(
            "/vehicle: Unhandled error, params=%s",
            params
        )
        return jsonify({
            "error": str(exc),
            "type": type(exc).__name__
        }), 500

if __name__ == "__main__":
    # dev/test-д зориулсан; prod дээр gunicorn ашиглана (README-г үз)
    app.run(host="0.0.0.0", port=8088)
