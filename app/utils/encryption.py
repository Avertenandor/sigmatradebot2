"""Encryption utilities for PII data."""

import base64

from cryptography.fernet import Fernet
from loguru import logger


class EncryptionService:
    """
    Encryption service for sensitive data.

    Uses Fernet (symmetric encryption) for PII protection.
    """

    def __init__(self, encryption_key: str | None = None) -> None:
        """
        Initialize encryption service.

        Args:
            encryption_key: Base64-encoded Fernet key
        """
        if encryption_key:
            try:
                self.fernet = Fernet(encryption_key.encode())
                self.enabled = True
            except Exception as e:
                logger.error(f"Invalid encryption key: {e}")
                self.fernet = None
                self.enabled = False
        else:
            self.fernet = None
            self.enabled = False

    def encrypt(self, plaintext: str) -> str | None:
        """
        Encrypt plaintext.

        Args:
            plaintext: Text to encrypt

        Returns:
            Encrypted text (base64) or None if disabled
        """
        if not self.enabled or not self.fernet:
            return plaintext

        try:
            encrypted = self.fernet.encrypt(plaintext.encode())
            return base64.b64encode(encrypted).decode()

        except Exception as e:
            logger.error(f"Encryption error: {e}")
            return None

    def decrypt(self, ciphertext: str) -> str | None:
        """
        Decrypt ciphertext.

        Args:
            ciphertext: Encrypted text (base64)

        Returns:
            Decrypted text or None if error
        """
        if not self.enabled or not self.fernet:
            return ciphertext

        try:
            encrypted = base64.b64decode(ciphertext.encode())
            decrypted = self.fernet.decrypt(encrypted)
            return decrypted.decode()

        except Exception as e:
            logger.error(f"Decryption error: {e}")
            return None

    @staticmethod
    def generate_key() -> str:
        """
        Generate new Fernet key.

        Returns:
            Base64-encoded key
        """
        return Fernet.generate_key().decode()


# Singleton instance
_encryption_service: EncryptionService | None = None


def get_encryption_service() -> EncryptionService | None:
    """Get encryption service singleton."""
    return _encryption_service


def init_encryption_service(
    encryption_key: str | None = None
) -> EncryptionService:
    """Initialize encryption service singleton."""
    global _encryption_service

    _encryption_service = EncryptionService(encryption_key)

    return _encryption_service
