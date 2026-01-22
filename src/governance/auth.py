"""Governance Auth - RBAC for endpoints (UAAL-inspired)

Self-Explanatory: Functions for user auth & role checks.
Why: Compliance moat - DPDP/RBAC for access.
How: Depends injection; base64 token for demo (prod: JWT + UAAL policy_engine).
Roles: 'admin' (full), 'pathologist' (read/write), 'viewer' (read-only).
"""

import base64
import json
from typing import Dict
from fastapi import Depends, HTTPException, Header
import structlog

logger = structlog.get_logger()

# Role mappings per endpoint (expandable)
ALLOWED_ROLES = {
    "upload": ["admin", "pathologist"],
    "retrieve": ["admin", "pathologist"],
    "list": ["admin", "pathologist", "viewer"],
    "metadata": ["admin", "pathologist", "viewer"],
    "delete": ["admin"]  # High-privilege action
}

def get_current_user(authorization: str = Header(None)) -> Dict[str, str]:
    """Get user from auth header (demo base64 decode)
    
    Args:
        authorization: 'Bearer <base64_token>'
    
    Returns:
        User dict {user_id, role}
    
    Raises:
        401 if invalid
    """
    if not authorization:
        logger.error("Missing auth header")
        raise HTTPException(status_code=401, detail="Authorization header missing")
    
    try:
        scheme, token = authorization.split()
        if scheme.lower() != "bearer":
            raise ValueError("Invalid scheme")
        user_data = base64.b64decode(token).decode("utf-8")
        user = json.loads(user_data)
        if "user_id" not in user or "role" not in user:
            raise ValueError("Invalid user data")
        logger.info("User authenticated", user_id=user["user_id"], role=user["role"])
        return user
    except Exception as e:
        logger.error("Auth error", error=str(e))
        raise HTTPException(status_code=401, detail="Invalid authentication")

def check_role(endpoint: str):
    """Dependency factory for role check based on endpoint
    
    Usage: Depends(check_role("upload"))
    """
    required_roles = ALLOWED_ROLES.get(endpoint, [])
    async def _check_role(user: Dict[str, str] = Depends(get_current_user)):
        if user["role"] not in required_roles:
            logger.warning("Role denied", user_role=user["role"], required=required_roles, endpoint=endpoint)
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return user
    return _check_role

# Integrate with UAAL: In prod, extend with policy_engine.py for dynamic policies.

ALLOWED_ROLES["ai_run"] = ["admin", "pathologist"]
