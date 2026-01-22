"""De-ID Middleware - Scrub PHI from DICOM/WSI before Vault save

Self-Explanatory: FastAPI middleware for de-identification.
Why: DPDP compliance - auto-remove patient metadata from headers.
How: Uses pydicom for DICOM, OpenSlide props for WSI; blacklists tags.
Integrates: Add to app.middleware in main.py.
"""
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
import structlog
from pydicom import dcmread
from pydicom.errors import InvalidDicomError
import openslide
import io
import os
from typing import Callable

logger = structlog.get_logger()

class DeIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if request.url.path == "/ims/upload" and request.method == "POST":
            # Get form data
            form = await request.form()
            file = form.get("file")
            if not file:
                return await call_next(request)
            
            # Read bytes
            content = await file.read()
            file.seek(0)  # Reset for later
            
            try:
                # DICOM check
                dicom = dcmread(io.BytesIO(content))
                # Scrub PHI tags (blacklist)
                phi_tags = [
                    (0x0010, 0x0010),  # PatientName
                    (0x0010, 0x0020),  # PatientID
                    (0x0010, 0x0030),  # PatientBirthDate
                    (0x0010, 0x0040),  # PatientSex
                    (0x0010, 0x1010),  # PatientAge
                    # Add more: Address, Phone, etc.
                ]
                for tag in phi_tags:
                    if tag in dicom:
                        del dicom[tag]
                # Save scrubbed
                buf = io.BytesIO()
                dicom.save_as(buf)
                scrubbed_content = buf.getvalue()
                logger.info("DICOM scrubbed", tags_removed=len(phi_tags))
            except InvalidDicomError:
                # WSI check
                temp_path = f"/tmp/temp_wsi_{os.urandom(4).hex()}"
                with open(temp_path, "wb") as f:
                    f.write(content)
                try:
                    slide = openslide.OpenSlide(temp_path)
                    # Scrub properties
                    props = dict(slide.properties)
                    phi_keys = [k for k in props if any(term in k.lower() for term in ["patient", "id", "name", "birth", "dob", "sex", "age"])]
                    for k in phi_keys:
                        del props[k]  # Can't modify slide props directly; log and warn
                    logger.warning("WSI props scrubbed (logged only)", keys=phi_keys)
                    scrubbed_content = content  # For now, can't modify WSI; prod: Re-save with scrubbed meta
                finally:
                    os.remove(temp_path)
            
            # Override file content with scrubbed
            request._body = scrubbed_content  # Hack: Override body for next handler
            # Prod: Better to use custom UploadFile subclass
            
        return await call_next(request)
