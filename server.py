# -*- coding: utf-8 -*-

import time
import logging

from flask import Flask, request, jsonify
from zeep.helpers import serialize_object

from XypClient import Service
from env import KEY_PATH, REGNUM

logging.basicConfig(level=logging.INFO)

app = Flask(__name__)

TRANSPORT_WSDL = "https://xyp.gov.mn/transport-1.3.0/ws?WSDL"
PROPERTY_WSDL = "https://xyp.gov.mn/property-1.3.0/ws?WSDL"


@app.get("/health")
def health():
    return jsonify({"status": "ok"})


@app.post("/vehicle")
def vehicle():

    body = request.get_json(force=True)

    num = body.get("num")

    if not num:
        return jsonify({"error": "num required"}), 400

    params = {
        "plateNumber": num, 
        "regnum": REGNUM,
    }

    try:
        svc = Service(
            TRANSPORT_WSDL,
            str(int(time.time())),
            pkey_path=KEY_PATH
        )

        result = svc.client.service.WS100401_getVehicleInfo(params)

        return jsonify(
            serialize_object(result)
        )

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.post("/property")
def property_list():

    body = request.get_json(force=True)

    regnum = body.get("regnum", REGNUM)

    params = {
        "auth": {
            "citizen": {
                "authType": 0,
                "certFingerprint": None,
                "civilId": None,
                "fingerprint": b"*** NO ACCESS ***",
                "regnum": regnum,
                "signature": None,
            },
            "operator": {
                "authType": 0,
                "certFingerprint": None,
                "civilId": None,
                "fingerprint": b"*** NO ACCESS ***",
                "regnum": None,
                "signature": None,
            },
        },
        "regnum": regnum,
    }

    try:

        svc = Service(
            PROPERTY_WSDL,
            str(int(time.time())),
            pkey_path=KEY_PATH
        )

        result = svc.client.service.WS100202_getPropertyList(params)

        return jsonify(
            serialize_object(result)
        )

    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=8088,
        debug=False
    )