"""IMS Router - Image Management System (upload & store slides)

Endpoints:
- /upload: Ingest slide, validate, de-ID, encrypt, store.
Why Modular: This router handles all IMS logic; plug into main app.
How Smooth: Async for large files, logs everything.
"""

from fastapi import APIRouter, UploadFile, File, HTTPException
import structlog
from src.utils.slide_utils import validate_slide, de_identify_slide, encrypt_data
import os
import uuid  # For unique IDs

router = APIRouter()
logger = structlog.get_logger()

@router.post("/upload")
async def upload_slide(file: UploadFile = File(...)):
    """Upload and process pathology slide
    
    Args:
        file: Uploaded WSI file (SVS/NDPI/MRXS)
    
    Returns:
        Dict with slide_id, status
    
    Flow (Layman): Like uploading a photo to cloud - check if it's a photo, blur names, lock it, save.
    Why: Core ingestion for PACS-like system.
    Governance Hook: De-ID here; later add UAAL sign.
    """
    try:
        # Step 1: Validate format & open
        slide = validate_slide(file)
        
        # Step 2: De-identify
        de_id_data = de_identify_slide(slide)
        
        # Step 3: Encrypt
        encrypted_data = encrypt_data(de_id_data)
        
        # Step 4: Store (demo: local file; prod: pvtvault)
        slide_id = str(uuid.uuid4())
        store_path = f"data/uploads/{slide_id}.enc"
        with open(store_path, "wb") as f:
            f.write(encrypted_data)
        
        logger.info("Slide uploaded successfully", slide_id=slide_id, original_name=file.filename)
        return {"slide_id": slide_id, "status": "uploaded", "message": "Processed and stored securely"}
    
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error("Upload error", error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/")
async def ims_home():
    return {"message": "PATHAI IMS - Your secure slide storage! Use /upload to ingest."}
