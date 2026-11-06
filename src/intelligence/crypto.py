"""
Fernet symmetric encryption for API key storage.
The encryption key lives in .env (SETTINGS_ENCRYPTION_KEY) — never in the DB.
"""
from cryptography.fernet import Fernet, InvalidToken

from src.config import settings


def _get_fernet() -> Fernet:
    key = settings.SETTINGS_ENCRYPTION_KEY
    if not key:
        raise RuntimeError(
            "SETTINGS_ENCRYPTION_KEY is not set. "
            "Generate one with: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
        )
    return Fernet(key.encode())


def encrypt_api_key(plain_key: str) -> str:
    """Encrypt a plain-text API key → base64 ciphertext string."""
    return _get_fernet().encrypt(plain_key.encode()).decode()


def decrypt_api_key(encrypted_key: str) -> str:
    """Decrypt a Fernet ciphertext → plain-text API key."""
    try:
        return _get_fernet().decrypt(encrypted_key.encode()).decode()
    except InvalidToken as exc:
        raise ValueError("Failed to decrypt API key — encryption key may have changed") from exc


def mask_api_key(plain_key: str) -> str:
    """Return a masked version for display: 'sk-••••••••abcd'."""
    if not plain_key or len(plain_key) < 8:
        return "••••••••"
    return plain_key[:4] + "••••••••" + plain_key[-4:]
