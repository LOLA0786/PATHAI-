"""IMS Router - Image Management System (upload, retrieve, list, metadata for slides)

Endpoints (all RBAC protected):
- /upload: Ingest slide (admin/pathologist only)
- /retrieve/{slide_id}: Fetch decrypted slide (admin/pathologist only)
- /list: List slides (admin/pathologist/viewer)
- /metadata/{slide_id}: Get metadata (admin/pathologist/viewer)
Why Modular: This router handles all IMS logic; plug into main app.
How Smooth: Async for large files, logs everything.
"""

from fastapi import APIRouter, UploadFile, File, HTTPException, Response, Depends
import structlog
from src.utils.slide_utils import (validate_slide, de_identify_slide, encrypt_data, decrypt_data,
                                   extract_metadata, save_metadata, load_metadata)
from src.governance.auth import check_role  # RBAC dependency
import os
import uuid  # For unique IDs
from typing import List, Dict, Any
from pydantic import BaseModel

router = APIRouter()
logger = structlog.get_logger()

# Enhanced model for list response (includes metadata)
class SlideInfo(BaseModel):
    slide_id: str
    file_path: str
    size_bytes: int
    metadata: Dict[str, Any]  # Flexible dict for dimensions, etc.

@router.post("/upload")
async def upload_slide(file: UploadFile = File(...), user: Dict[str, str] = Depends(check_role("upload"))):
    """Upload and process pathology slide with metadata
    
    Args:
        file: Uploaded WSI file (SVS/NDPI/MRXS)
    
    Returns:
        Dict with slide_id, status
    """
    try:
        # Step 1: Validate format & open
        slide = validate_slide(file)
        
        # Step 2: Extract metadata (before de-ID, but safe)
        metadata = extract_metadata(slide, file.filename)
        
        # Step 3: De-identify
        de_id_data = de_identify_slide(slide)
        
        # Step 4: Encrypt
        encrypted_data = encrypt_data(de_id_data)
        
        # Step 5: Store encrypted data & metadata
        slide_id = str(uuid.uuid4())
        store_path = f"data/uploads/{slide_id}.enc"
        with open(store_path, "wb") as f:
            f.write(encrypted_data)
        save_metadata(slide_id, metadata)
        
        logger.info("Slide uploaded successfully", slide_id=slide_id, original_name=file.filename, user_id=user["user_id"])
        return {"slide_id": slide_id, "status": "uploaded", "message": "Processed, metadata stored securely"}
    
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error("Upload error", error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/retrieve/{slide_id}")
async def retrieve_slide(slide_id: str, user: Dict[str, str] = Depends(check_role("retrieve"))):
    """Retrieve decrypted slide by ID
    
    Args:
        slide_id: UUID from upload
    
    Returns:
        FileResponse with decrypted bytes
    """
    store_path = f"data/uploads/{slide_id}.enc"
    if not os.path.exists(store_path):
        logger.error("Slide not found", slide_id=slide_id)
        raise HTTPException(status_code=404, detail="Slide not found")
    try:
        with open(store_path, "rb") as f:
            encrypted_data = f.read()
        decrypted_data = decrypt_data(encrypted_data)
        logger.info("Slide retrieved successfully", slide_id=slide_id, user_id=user["user_id"])
        return Response(content=decrypted_data, media_type="application/octet-stream", 
                        headers={"Content-Disposition": f"attachment; filename={slide_id}.png"})
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error("Retrieve error", error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/list", response_model=List[SlideInfo])
async def list_slides(limit: int = 50, offset: int = 0, user: Dict[str, str] = Depends(check_role("list"))):
    """List all stored slide IDs with metadata
    
    Args:
        limit: Max number to return (pagination)
        offset: Start from this index
    
    Returns:
        List of SlideInfo (slide_id, file_path, size, metadata)
    """
    upload_dir = "data/uploads"
    if not os.path.exists(upload_dir):
        logger.info("No uploads directory found", dir=upload_dir)
        return []
    
    try:
        all_files = [f for f in os.listdir(upload_dir) if f.endswith(".enc")]
        all_files.sort()  # Consistent order
        
        # Paginate
        paginated_files = all_files[offset:offset + limit]
        
        slides = []
        for filename in paginated_files:
            slide_id = filename.replace(".enc", "")
            path = os.path.join(upload_dir, filename)
            size = os.path.getsize(path)
            metadata = load_metadata(slide_id)
            slides.append(SlideInfo(slide_id=slide_id, file_path=path, size_bytes=size, metadata=metadata))
        
        logger.info("Slides listed", count=len(slides), total=len(all_files), offset=offset, limit=limit, user_id=user["user_id"])
        return slides
    
    except Exception as e:
        logger.error("List error", error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/metadata/{slide_id}")
async def get_metadata(slide_id: str, user: Dict[str, str] = Depends(check_role("metadata"))):
    """Get metadata for a specific slide by ID (RBAC protected)
    
    Args:
        slide_id: UUID from upload
    
    Returns:
        Dict with metadata (dimensions, upload_time, etc.)
    """
    try:
        metadata = load_metadata(slide_id)
        logger.info("Metadata retrieved", slide_id=slide_id, user_id=user["user_id"])
        return metadata
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error("Metadata retrieve error", error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/")
async def ims_home():
    return {"message": "PATHAI IMS - Your secure slide storage! All endpoints RBAC-protected."}
