"""Fernet encryption for sensitive data at rest."""

import base64
import hashlib
import os

from src.utils.logger import get_logger

logger = get_logger(__name__)

_ENCRYPTION_KEY = None


def _get_key() -> bytes:
    """Derive a Fernet-compatible key from the environment secret."""
    global _ENCRYPTION_KEY
    if _ENCRYPTION_KEY is None:
        secret = os.getenv("MEDGUARD_ENCRYPTION_KEY", "medguard-default-key")
        _ENCRYPTION_KEY = base64.urlsafe_b64encode(hashlib.sha256(secret.encode()).digest())
    return _ENCRYPTION_KEY


def encrypt_data(plaintext: str) -> str:
    """Encrypt a string using Fernet (AES-128-CBC + HMAC)."""
    try:
        from cryptography.fernet import Fernet

        f = Fernet(_get_key())
        return f.encrypt(plaintext.encode()).decode()
    except ImportError:
        # Fallback: base64 encoding (not secure, for dev only)
        logger.warning("cryptography not installed, using base64 fallback")
        return base64.b64encode(plaintext.encode()).decode()


def decrypt_data(ciphertext: str) -> str:
    """Decrypt a Fernet-encrypted string."""
    try:
        from cryptography.fernet import Fernet

        f = Fernet(_get_key())
        return f.decrypt(ciphertext.encode()).decode()
    except ImportError:
        return base64.b64decode(ciphertext.encode()).decode()
