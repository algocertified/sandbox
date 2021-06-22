import base64

from algosdk.encoding import decode_address
from nacl.signing import SigningKey, VerifyKey


def create_message(tasa_id: str) -> bytes:
    message = tasa_id.encode()
    message = base64.b64encode(message)
    
    return message


def sign_message(message: bytes, secret_key: str) -> bytes:
    secret_key = base64.b64decode(secret_key)
    signing_key = SigningKey(secret_key[:32])  # key_len_bytes = 32
    signed = signing_key.sign(message=message)
    
    return signed.signature


def verify_message(message: bytes, public_key: str, signature: bytes) -> bool:
    public_key = decode_address(public_key)
    verifying_key = VerifyKey(public_key)
    
    return verifying_key.verify(message, signature) == message