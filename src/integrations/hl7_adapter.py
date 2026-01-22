"""LIS/HIS Integration - HL7 Adapter with Signed Logs

Self-Explanatory: Bi-directional HL7 v2.x handling.
Why: Seamless lab workflow integration.
How: hl7apy for parse/generate; call audit_logger with signature on every message.
Endpoints: /hl7/receive (POST for incoming), send via async.
"""
from hl7apy.core import Message
from hl7apy.validation import VALIDATION_LEVEL
from fastapi import APIRouter, HTTPException, Body
import structlog
from src.governance.audit_logger import log_audit
from src.governance.auth import check_role
from cryptography.hmac import HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend
import base64

router = APIRouter(prefix="/hl7", tags=["LIS"])
logger = structlog.get_logger()
KEY = b'lis_sign_key'  # Prod: KMS

def sign_message(msg: str) -> str:
    hmac = HMAC(KEY, hashes.SHA256(), default_backend())
    hmac.update(msg.encode())
    return base64.b64encode(hmac.finalize()).decode()

@router.post("/receive")
async def receive_hl7(msg: str = Body(...), user: dict = Depends(check_role("lis_receive"))):
    """Receive HL7 message (e.g., ORM order)"""
    try:
        hl7_msg = Message(msg, validation_level=VALIDATION_LEVEL.TOLERANT)
        hl7_msg.validate()
        
        # Process: e.g., if ORM, trigger slide upload workflow
        action = hl7_msg.msh.msh_9.value  # Message type
        resource_id = hl7_msg.pid.pid_3.value  # Patient ID (de-ID later)
        
        # Sign & log
        signature = sign_message(msg)
        log_audit(user['user_id'], 'hl7_receive', resource_id, {'type': action, 'signature': signature})
        
        # Demo response: ACK
        ack = Message("ACK")
        ack.msh.msh_9 = "ACK"
        ack.msh.msh_10 = "ACK_ID"
        ack.msa.msa_1 = "AA"  # Accept
        return {"ack": ack.to_er7()}
    except Exception as e:
        logger.error("HL7 receive error", error=str(e))
        raise HTTPException(400, "Invalid HL7")

async def send_hl7(to_lis_url: str, hl7_msg: Message, user_id: str):
    """Send HL7 (e.g., ORU report) async"""
    msg_str = hl7_msg.to_er7()
    signature = sign_message(msg_str)
    log_audit(user_id, 'hl7_send', 'report_id', {'type': 'ORU', 'signature': signature})
    
    # Post to LIS (httpx async)
    import httpx
    async with httpx.AsyncClient() as client:
        resp = await client.post(to_lis_url, data=msg_str)
    return resp.text

# Support ORU (reports), ORM (orders), ADT (admissions)
# Integrate: Call send_hl7 after AI/report gen.
