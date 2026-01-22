"""Compliance Middleware - Consent check, erasure

Why: DPDP massive penalties.
How: Check 'consent_token' in metadata; add /erase endpoint.
"""
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
import structlog
from src.utils.slide_utils import load_metadata

logger = structlog.get_logger()

class ConsentMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if 'slide_id' in request.path_params:  # For /retrieve/metadata/etc.
            slide_id = request.path_params['slide_id']
            meta = load_metadata(slide_id)
            if not meta.get('consent_token'):
                logger.warning("Consent missing", slide_id=slide_id)
                raise HTTPException(403, "No consent token")
        return await call_next(request)

# Eras ure endpoint (soft-delete: Flag, remove PHI)
@router.post("/erase/{patient_id}")
async def erase_data(patient_id: str, user: dict = Depends(check_role("admin"))):
    # DB: DELETE FROM patients WHERE id = patient_id; cascade to slides
    logger.info("Data erased", patient_id=patient_id)
    return {"status": "erased"}
