"""Viewer Router - Tile streaming, annotations, tele-review WS

Endpoints:
- /info/{slide_id}
- /tile/{slide_id}/{level}/{x}/{y}
- /annotations/{slide_id}: Get/post annotations
WS: /ws/tele/{slide_id}: Join room, broadcast ann updates
"""
from fastapi import APIRouter, HTTPException, Response, Depends, Body
import structlog
from src.utils.slide_utils import load_metadata, decrypt_data, add_annotation, get_annotations
from src.utils.viewer_utils import get_tile
from src.governance.auth import check_role
from src.main import sio  # SocketIO
import openslide
import io
import os

router = APIRouter()
logger = structlog.get_logger()

# ... (keep existing /info, /tile)

@router.get("/annotations/{slide_id}")
async def get_slide_annotations(slide_id: str, user: Dict[str, str] = Depends(check_role("metadata"))):
    anns = get_annotations(slide_id)
    return {"annotations": anns}

@router.post("/annotations/{slide_id}")
async def post_annotation(slide_id: str, annotation: Dict = Body(...), user: Dict[str, str] = Depends(check_role("upload"))):  # Write role
    annotation["user_id"] = user["user_id"]  # Track who added
    add_annotation(slide_id, annotation)
    # Broadcast to WS room
    await sio.emit("new_annotation", annotation, room=slide_id)
    logger.info("Annotation posted & broadcast", slide_id=slide_id, user_id=user["user_id"])
    return {"status": "added"}

# WS for tele-review (multi-user)
@sio.on("connect")
async def connect(sid, environ):
    logger.info("WS connected", sid=sid)

@sio.on("join_tele")
async def join_tele(sid, data):
    slide_id = data.get("slide_id")
    if slide_id:
        await sio.enter_room(sid, slide_id)
        anns = get_annotations(slide_id)
        await sio.emit("initial_annotations", anns, to=sid)
        logger.info("Joined tele room", sid=sid, slide_id=slide_id)

@sio.on("disconnect")
async def disconnect(sid):
    logger.info("WS disconnected", sid=sid)

@router.get("/")
async def viewer_home():
    return {"message": "PATHAI Viewer - Annotations & tele-review enabled!"}
