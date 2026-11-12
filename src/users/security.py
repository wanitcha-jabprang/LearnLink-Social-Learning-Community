
import os

from cryptography.fernet import Fernet, InvalidToken
from django.core.exceptions import ImproperlyConfigured


def get_mfa_cipher():
    """Return the Fernet cipher configured for MFA secret encryption."""
    key = os.environ.get("MFA_ENCRYPTION_KEY")

    if not key:
        raise ImproperlyConfigured(
            "MFA_ENCRYPTION_KEY is not configured."
        )

    try:
        return Fernet(key.encode("utf-8"))
    except (ValueError, TypeError) as exc:
        raise ImproperlyConfigured(
            "MFA_ENCRYPTION_KEY is invalid."
        ) from exc


def encrypt_mfa_secret(secret: str) -> str:
    """Encrypt a TOTP secret before storing it."""
    if not secret:
        raise ValueError("MFA secret cannot be empty.")

    cipher = get_mfa_cipher()
    return cipher.encrypt(secret.encode("utf-8")).decode("utf-8")


def decrypt_mfa_secret(encrypted_secret: str) -> str:
    """Decrypt a stored TOTP secret for OTP verification."""
    if not encrypted_secret:
        raise ValueError("Encrypted MFA secret cannot be empty.")

    cipher = get_mfa_cipher()

    try:
        return cipher.decrypt(
            encrypted_secret.encode("utf-8")
        ).decode("utf-8")
    except (InvalidToken, UnicodeDecodeError) as exc:
        raise ValueError(
            "Unable to decrypt MFA secret."
        ) from exc
