from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken


def _fernet(secret: str) -> Fernet:
    digest = hashlib.sha256(secret.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_secret(plaintext: str, app_secret: str) -> str:
    if not plaintext:
        return ""
    return _fernet(app_secret).encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt_secret(token: str, app_secret: str) -> str:
    if not token:
        return ""
    try:
        return _fernet(app_secret).decrypt(token.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise ValueError("Unable to decrypt API key") from exc


def mask_secret(plaintext: str) -> str:
    if not plaintext:
        return ""
    if len(plaintext) <= 8:
        return "*" * len(plaintext)
    return f"{plaintext[:3]}…{plaintext[-4:]}"
