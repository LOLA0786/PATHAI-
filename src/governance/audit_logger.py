"""Audit Logger - Non-repudiable trail

Why: NABL/DPDP audits.
How: Append-only to Postgres, sign entries.
"""
import structlog
from src.utils.slide_utils import ENCRYPTION_KEY  # Reuse for signing
from cryptography.hmac import HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend
# Assume DB connection
from sqlalchemy import create_engine, text

engine = create_engine('postgresql://admin:securepass@pathai-db:5432/pathai')
logger = structlog.get_logger()

def log_audit(user_id: str, action: str, resource_id: str, details: dict):
    hmac = HMAC(ENCRYPTION_KEY, hashes.SHA256(), default_backend())
    msg = f"{user_id}|{action}|{resource_id}|{details}"
    hmac.update(msg.encode())
    signature = hmac.finalize().hex()
    
    with engine.connect() as conn:
        conn.execute(text("INSERT INTO audit_logs (user_id, action, resource_id, details, signature) VALUES (:u, :a, :r, :d, :s)"),
                     {"u": user_id, "a": action, "r": resource_id, "d": details, "s": signature})
    logger.info("Audit logged", signature=signature)

# Call in all endpoints (e.g., upload: log_audit(user['user_id'], 'upload_slide', slide_id, {'file': file.filename}))
