"""End-to-End Encryption - TLS/field-level

Why: Secure PHI.
How: Fernet for fields; TLS in ingress.
"""
from cryptography.fernet import Fernet
import structlog

logger = structlog.get_logger()
KEY = Fernet.generate_key()  # KMS prod

def encrypt_field(data: str) -> str:
    f = Fernet(KEY)
    return f.encrypt(data.encode()).decode()

def decrypt_field(encrypted: str) -> str:
    f = Fernet(KEY)
    return f.decrypt(encrypted.encode()).decode()

# Rotation: Script to re-encrypt with new key quarterly.
