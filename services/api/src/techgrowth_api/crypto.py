import base64
import hashlib
import hmac

from cryptography.fernet import Fernet


def token_hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def constant_time_matches(raw: str, expected_hash: str) -> bool:
    return hmac.compare_digest(token_hash(raw), expected_hash)


class SecretCipher:
    def __init__(self, installation_secret: str) -> None:
        key = base64.urlsafe_b64encode(hashlib.sha256(installation_secret.encode()).digest())
        self._fernet = Fernet(key)

    def encrypt(self, value: str) -> str:
        return self._fernet.encrypt(value.encode()).decode()

    def decrypt(self, value: str) -> str:
        return self._fernet.decrypt(value.encode()).decode()
