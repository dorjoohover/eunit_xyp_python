# -*- coding: utf-8 -*-
"""Minimal XYP SOAP caller close to the official sample.

Examples:
    python3 SimpleRequest.py \
        --service-group transport \
        --version 1.3.0 \
        --operation WS100401_getVehicleInfo \
        --plate-number 4836УАТ

    python3 SimpleRequest.py \
        --service-group property \
        --version 1.3.0 \
        --operation WS100202_getPropertyList \
        --regnum ИХ97070415
"""

import argparse
import json
import os
import time
from base64 import b64encode

import urllib3
from Crypto.Hash import SHA256
from Crypto.PublicKey import RSA
from Crypto.Signature import PKCS1_v1_5
from requests import Session
from zeep import Client
from zeep.helpers import serialize_object
from zeep.transports import Transport

from env import ACCESS_TOKEN, CERT_PATH, KEY_PATH


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
    return f"https://xyp.gov.mn/{service_group}-{version}/ws?WSDL"


class XypSign:
    def __init__(self, key_path):
        self.key_path = resolve_existing_path(key_path)

    def __get_priv_key(self):
        with open(self.key_path, "rb") as keyfile:
            return RSA.importKey(keyfile.read())

    def __timestamp(self):
        return str(int(time.time()))

    def __to_be_signed(self, access_token):
        return {
            "accessToken": access_token,
            "timeStamp": self.__timestamp(),
        }

    def __build_param(self, to_be_signed):
        return to_be_signed["accessToken"] + "." + to_be_signed["timeStamp"]

    def sign(self, access_token):
        to_be_signed = self.__to_be_signed(access_token)
        digest = SHA256.new()
        digest.update(self.__build_param(to_be_signed).encode("utf8"))
        signature = b64encode(PKCS1_v1_5.new(self.__get_priv_key()).sign(digest))
        return to_be_signed, signature


class Service:
    def __init__(self, wsdl, access_token, pkey_path, cert_path=None):
        self.__access_token = access_token
        self.__to_be_signed, self.__signature = XypSign(pkey_path).sign(access_token)

        urllib3.disable_warnings()
        session = Session()
        session.verify = False

        resolved_key_path = resolve_existing_path(pkey_path)
        resolved_cert_path = resolve_existing_path(cert_path)
        if resolved_cert_path and resolved_key_path:
            session.cert = (resolved_cert_path, resolved_key_path)

        transport = Transport(session=session)
        self.client = Client(wsdl, transport=transport)
        self.client.transport.session.headers.update({
            "accessToken": self.__access_token,
            "timeStamp": self.__to_be_signed["timeStamp"],
            "signature": self.__signature.decode("ascii"),
        })

    def dump(self, operation, params=None):
        if params:
            response = self.client.service[operation](params)
        else:
            response = self.client.service[operation]()

        result = serialize_object(response)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return result


def parse_args():
    parser = argparse.ArgumentParser(description="Direct XYP SOAP caller")
    parser.add_argument("--wsdl", help="Full WSDL URL. Overrides service-group/version.")
    parser.add_argument(
        "--service-group",
        default="transport",
        choices=["property", "transport"],
        help="XYP service group",
    )
    parser.add_argument(
        "--version",
        default="1.3.0",
        help="XYP service version such as 1.3.0, 1.4.0, 1.5.0",
    )
    parser.add_argument("--operation", required=True, help="SOAP operation name")
    parser.add_argument(
        "--params",
        help='Raw JSON object, for example: {"plateNumber":"4836УАТ"}',
    )
    parser.add_argument("--plate-number")
    parser.add_argument("--cabin-number")
    parser.add_argument("--certificat-number")
    parser.add_argument("--regnum")
    parser.add_argument("--access-token", default=ACCESS_TOKEN)
    parser.add_argument("--key-path", default=KEY_PATH)
    parser.add_argument("--cert-path", default=CERT_PATH)
    return parser.parse_args()


def build_params(args):
    if args.params:
        parsed = json.loads(args.params)
        if not isinstance(parsed, dict):
            raise ValueError("--params must be a JSON object")
        return parsed

    params = {}

    if args.plate_number:
        params["plateNumber"] = str(args.plate_number).strip().upper()

    if args.cabin_number:
        params["cabinNumber"] = str(args.cabin_number).strip()

    if args.certificat_number:
        params["certificatNumber"] = str(args.certificat_number).strip()

    if args.regnum:
        params["regnum"] = str(args.regnum).strip()

    return params or None


def main():
    args = parse_args()
    wsdl = args.wsdl or build_wsdl_url(args.service_group, args.version)
    params = build_params(args)

    service = Service(
        wsdl=wsdl,
        access_token=args.access_token,
        pkey_path=args.key_path,
        cert_path=args.cert_path,
    )
    service.dump(args.operation, params)


if __name__ == "__main__":
    main()
