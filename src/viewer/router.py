"""Viewer Router - WSI tile streaming & info

Endpoints:
- /info/{slide_id}: Get slide dimensions, levels (for client setup)
- /tile/{slide_id}/{level}/{x}/{y}: Get PNG tile at coords (RBAC protected)
Why: Cloud+edge viewing - streams tiles for zoom/pan.
How: Integrates IMS decrypt, OpenSlide tiling.
Client: Use OpenLayers/Leaflet for frontend (not included here).
"""

from fastapi import APIRouter, HTTPException, Response, Depends
import structlog
from src.utils.slide_utils import load_metadata, decrypt_data
from src.utils.viewer_utils import get_tile
from src.governance.auth import check_role
import os
import openslide
import io

router = APIRouter()
logger = structlog.get_logger()

@router.get("/info/{slide_id}")
async def get_slide_info(slide_id: str, user: Dict[str, str] = Depends(check_role("metadata"))):  # Reuse metadata role
    """Get slide info for viewer setup (dims, levels)
    
    Returns:
        Dict with width, height, levels, tile_size
    """
    try:
        metadata = load_metadata(slide_id)
        # Enhance with live levels if needed (from decrypted)
        enc_path = f"data/uploads/{slide_id}.enc"
        with open(enc_path, "rb") as f:
            encrypted_data = f.read()
        decrypted_data = decrypt_data(encrypted_data)
        temp_path = f"/tmp/{slide_id}.tmp"
        with open(temp_path, "wb") as temp_f:
            temp_f.write(decrypted_data)
        slide = openslide.OpenSlide(temp_path)
        info = {
            "width": slide.dimensions[0],
            "height": slide.dimensions[1],
            "levels": slide.level_count,
            "tile_size": 256  # Fixed for demo
        }
        logger.info("Slide info retrieved", slide_id=slide_id, user_id=user["user_id"])
        return info
    except Exception as e:
        logger.error("Info error", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to get slide info")
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)

@router.get("/tile/{slide_id}/{level}/{x}/{y}")
async def get_slide_tile(slide_id: str, level: int, x: int, y: int, user: Dict[str, str] = Depends(check_role("retrieve"))):
    """Stream tile PNG at level/x/y
    
    Args:
        slide_id, level, x, y
    
    Returns:
        PNG Response
    """
    tile_bytes = get_tile(slide_id, level, x, y)
    return Response(content=tile_bytes, media_type="image/png")

@router.get("/")
async def viewer_home():
    return {"message": "PATHAI Viewer - Stream tiles! Use /info/{id} and /tile/{id}/{level}/{x}/{y}"}
