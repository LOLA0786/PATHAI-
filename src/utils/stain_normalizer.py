"""Bharat-Stain Normalizer - Pre-process for consistent H&E

Why: Handle staining variations across Indian labs.
How: Demo histogram eq; prod: GAN (PyTorch CycleGAN).
Call in upload before de-ID.
"""
from skimage.exposure import equalize_hist
from PIL import Image
import io
import numpy as np
import structlog

logger = structlog.get_logger()

def normalize_stain(tile_bytes: bytes) -> bytes:
    img = Image.open(io.BytesIO(tile_bytes)).convert("RGB")
    img_np = np.array(img)
    norm = equalize_hist(img_np) * 255
    norm_img = Image.fromarray(norm.astype(np.uint8))
    buf = io.BytesIO()
    norm_img.save(buf, format="PNG")
    logger.info("Stain normalized")
    return buf.getvalue()
