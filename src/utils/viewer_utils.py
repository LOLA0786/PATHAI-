"""Viewer Utils - Tile extraction for WSI streaming

Self-Explanatory: Functions to get tiles from slides.
Why: Google Maps-style zoom/pan on large WSIs.
How: Uses OpenSlide on decrypted data (from IMS).
Note: Temp saves decrypted for OpenSlide (prod: memory/stream).
"""

import os
from typing import Tuple
import openslide
from PIL import Image
import io
import structlog
from src.utils.slide_utils import decrypt_data

logger = structlog.get_logger()

def get_tile(slide_id: str, level: int, x: int, y: int, tile_size: Tuple[int, int] = (256, 256)) -> bytes:
    """Extract a tile PNG bytes from slide at level/x/y
    
    Args:
        slide_id: UUID of stored slide
        level: Zoom level (0 = full res)
        x, y: Tile coordinates
        tile_size: Pixel size (default 256x256)
    
    Returns:
        PNG bytes of tile
    
    Flow (Layman): Like getting a map square - zoom level, position, cut image piece.
    Why: Streaming - client requests tiles as user zooms/pans.
    Governance: Assumes caller has RBAC (checked in router).
    """
    enc_path = f"data/uploads/{slide_id}.enc"
    if not os.path.exists(enc_path):
        logger.error("Slide not found for tiling", slide_id=slide_id)
        raise HTTPException(status_code=404, detail="Slide not found")
    
    try:
        with open(enc_path, "rb") as f:
            encrypted_data = f.read()
        decrypted_data = decrypt_data(encrypted_data)
        
        # Temp save for OpenSlide (prod: use openslide.OpenSlide(io.BytesIO(decrypted_data)) if supported)
        temp_path = f"/tmp/{slide_id}.tmp"
        with open(temp_path, "wb") as temp_f:
            temp_f.write(decrypted_data)
        
        slide = openslide.OpenSlide(temp_path)
        
        # Validate level/x/y
        if level >= slide.level_count or level < 0:
            raise ValueError("Invalid level")
        tile = slide.read_region((x * tile_size[0], y * tile_size[1]), level, tile_size)
        
        # Convert to PNG bytes
        buf = io.BytesIO()
        tile.convert("RGB").save(buf, format="PNG")
        tile_bytes = buf.getvalue()
        
        logger.info("Tile generated", slide_id=slide_id, level=level, x=x, y=y, size=len(tile_bytes))
        return tile_bytes
    
    except Exception as e:
        logger.error("Tile error", error=str(e), slide_id=slide_id)
        raise HTTPException(status_code=500, detail="Tile generation failed")
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)  # Clean up
