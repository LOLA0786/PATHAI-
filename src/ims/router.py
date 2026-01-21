"""IMS Router - Image Management System (upload & store slides)

Endpoints:
- /upload: Ingest slide, validate, de-ID, encrypt, store.
- /retrieve/{slide_id}: Fetch encrypted slide, decrypt, return as bytes.
Why Modular: This router handles all IMS logic; plug into main app.
How Smooth: Async for large files, logs everything.
"""

from fastapi import APIRouter, UploadFile, File, HTTPException, Response
import structlog
from src.utils.slide_utils import validate_slide, de_identify_slide, encrypt_data, decrypt_data
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

@router.get("/retrieve/{slide_id}")
async def retrieve_slide(slide_id: str):
    """Retrieve decrypted slide by ID
    
    Args:
        slide_id: UUID from upload
    
    Returns:
        FileResponse with decrypted bytes (as 'application/octet-stream')
    
    Flow (Layman): Like downloading a locked photo - unlock and send.
    Why: Access stored slides for viewer/AI.
    Governance: Log access; later add auth (UAAL/RBAC).
    Note: Returns bytes; client saves as .png or processes.
    """
    store_path = f"data/uploads/{slide_id}.enc"
    if not os.path.exists(store_path):
        logger.error("Slide not found", slide_id=slide_id)
        raise HTTPException(status_code=404, detail="Slide not found")
    
    try:
        with open(store_path, "rb") as f:
            encrypted_data = f.read()
        
        decrypted_data = decrypt_data(encrypted_data)
        
        logger.info("Slide retrieved successfully", slide_id=slide_id)
        # Return as binary response (client can save/process)
        return Response(content=decrypted_data, media_type="application/octet-stream", headers={"Content-Disposition": f"attachment; filename={slide_id}.png"})
    
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error("Retrieve error", error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/")
async def ims_home():
    return {"message": "PATHAI IMS - Your secure slide storage! Use /upload or /retrieve/{id}"}
