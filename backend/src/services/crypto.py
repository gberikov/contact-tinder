"""Token encryption at rest (Constitution Principle I, FR-002).

Uses Fernet (AES-128-CBC + HMAC) authenticated symmetric encryption. The key comes from the
TOKEN_ENCRYPTION_KEY env secret and is never logged or persisted in plaintext.
"""
from __future__ import annotations

from cryptography.fernet import Fernet

from src.core.config import get_settings

KEY_ID = "v1"


def _fernet() -> Fernet:
    key = get_settings().token_encryption_key
    if not key:
        raise RuntimeError("TOKEN_ENCRYPTION_KEY is not configured")
    return Fernet(key.encode() if isinstance(key, str) else key)


def encrypt(plaintext: str | None) -> bytes | None:
    if plaintext is None:
        return None
    return _fernet().encrypt(plaintext.encode())


def decrypt(ciphertext: bytes | None) -> str | None:
    if ciphertext is None:
        return None
    return _fernet().decrypt(bytes(ciphertext)).decode()
