from base64 import b64decode
from Crypto.Hash import SHA256
from Crypto.PublicKey import RSA
from Crypto.Signature import PKCS1_v1_5

ACCESS_TOKEN = "95b3a82a5ae64c208cfaed0d56b7563c"
TIMESTAMP = "1785867815"
SIGNATURE = "3dab0370f2cd4843aff30d1eb074646009e0b386b9c867a810863532e091eb66"

with open("certificate.crt", "rb") as file:
    public_key = RSA.import_key(file.read())

message = f"{ACCESS_TOKEN}.{TIMESTAMP}".encode("utf-8")
digest = SHA256.new(message)
signature_bytes = b64decode(SIGNATURE)

valid = PKCS1_v1_5.new(public_key).verify(digest, signature_bytes)
print("Signature valid:", valid)