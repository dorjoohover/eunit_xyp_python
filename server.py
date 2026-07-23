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

import urllib3
from flask import Flask, request, jsonify, abort
from requests import Session
from zeep import Client
from zeep.transports import Transport
from zeep.helpers import serialize_object
from Crypto.Hash import SHA256
from Crypto.Signature import PKCS1_v1_5
from Crypto.PublicKey import RSA

from env import ACCESS_TOKEN, KEY_PATH

urllib3.disable_warnings()

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
        return to_be_signed, signature


class XypService:
    """Жинхэнэ SOAP client — импорт хийхэд шууд дуудалт хийхгүй,
    зөвхөн ашиглах үед л client үүсгэнэ (client.py-ийн импортын side-effect
    асуудлыг давтахгүйн тулд)."""

    def __init__(self, wsdl, access_token, key_path):
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

    def call(self, operation, params=None):
        if params:
            return self.client.service[operation](params)
        return self.client.service[operation]()


app = Flask(__name__)


@app.get("/health")
def health():
    return jsonify({"status": "ok"}), 200


@app.post("/vehicle")
def vehicle():
    body = request.get_json(silent=True)
    if not body or not body.get("num"):
        abort(400, description="Missing `num` field")

    num = str(body["num"])

    if not ACCESS_TOKEN or not KEY_PATH:
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

    try:
        service = XypService(VEHICLE_WSDL, ACCESS_TOKEN, KEY_PATH)
        res = service.call("WS100401_getVehicleInfo", params)
        res_dict = serialize_object(res)
        return jsonify({"vehicle": res_dict}), 200
    except Exception as e:
        print("vehicle error:", str(e))
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    # dev/test-д зориулсан; prod дээр gunicorn ашиглана (README-г үз)
    app.run(host="0.0.0.0", port=8088)
