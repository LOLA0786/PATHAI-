"""Slide Utils - Shared functions for handling pathology slides

Self-Explanatory: Functions to validate, de-ID, and process WSI files.
Why: Keeps IMS clean; reusable for viewer/AI later.
How: Uses OpenSlide for format check, pytesseract for OCR redaction.
"""

import os
from typing import Optional
from fastapi import UploadFile, HTTPException
import openslide
import pytesseract
from PIL import Image
import numpy as np
import structlog
from cryptography.fernet import Fernet  # For encryption demo (real: integrate pvtvault)

logger = structlog.get_logger()

# Generate a key for demo encryption (in prod, use secure key management from pvtvault)
ENCRYPTION_KEY = Fernet.generate_key()
cipher = Fernet(ENCRYPTION_KEY)

def validate_slide(file: UploadFile) -> Optional[openslide.OpenSlide]:
    """Validate if uploaded file is a supported WSI format (SVS/NDPI/MRXS)
    
    Args:
        file: Uploaded file object
    
    Returns:
        OpenSlide object if valid, else raises HTTPException
    
    Why: Ensures only proper slides are ingested to avoid crashes later.
    """
    supported_formats = ['.svs', '.ndpi', '.mrxs']
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in supported_formats:
        logger.error("Invalid file format", filename=file.filename, ext=ext)
        raise HTTPException(status_code=400, detail=f"Unsupported format: {ext}. Use SVS/NDPI/MRXS.")
    
    # Save temp for OpenSlide check
    temp_path = f"/tmp/{file.filename}"
    with open(temp_path, "wb") as temp_file:
        temp_file.write(file.file.read())
    
    try:
        slide = openslide.OpenSlide(temp_path)
        logger.info("Slide validated", filename=file.filename, dimensions=slide.dimensions)
        return slide
    except openslide.OpenSlideError as e:
        logger.error("OpenSlide error", error=str(e))
        raise HTTPException(status_code=400, detail="Invalid slide file.")
    finally:
        os.remove(temp_path)  # Clean up

def de_identify_slide(slide: openslide.OpenSlide) -> bytes:
    """De-identify: OCR detect & redact labels/metadata from slide thumbnail
    
    Args:
        slide: Valid OpenSlide object
    
    Returns:
        De-identified slide data as bytes (for storage)
    
    Why: DPDP compliance - remove any PHI (names, IDs) via OCR on labels.
    How: Extract thumbnail, OCR text, black out detected areas.
    Note: Simplistic; enhance with better ML for prod.
    """
    # Get thumbnail for OCR (faster than full slide)
    thumbnail = slide.get_thumbnail((500, 500))  # Small size for quick process
    text = pytesseract.image_to_string(thumbnail)
    logger.info("OCR detected text", text=text.strip())
    
    if text:  # If text found, redact (black box over image areas)
        # Demo: Convert to array, black out whole image if text (prod: targeted boxes)
        img_array = np.array(thumbnail)
        img_array.fill(0)  # Black out (simplistic)
        redacted_img = Image.fromarray(img_array)
        logger.warning("Redaction applied", reason="Text detected")
    else:
        redacted_img = thumbnail
    
    # Save as bytes (in prod, apply to full slide levels)
    redacted_img.save("temp_redacted.png")  # Temp save
    with open("temp_redacted.png", "rb") as f:
        data = f.read()
    os.remove("temp_redacted.png")
    return data

def encrypt_data(data: bytes) -> bytes:
    """Encrypt data for storage (demo; integrate pvtvault core)
    
    Why: Secure vault storage as per plan.
    """
    encrypted = cipher.encrypt(data)
    logger.info("Data encrypted", size=len(encrypted))
    return encrypted

# More utils can be added later, e.g., metadata extraction
