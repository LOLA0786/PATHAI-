"""Viewer Router - Handles WSI viewing logic"""

from fastapi import APIRouter

router = APIRouter()

@router.get("/")
async def viewer_home():
    return {"message": "PATHAI Viewer - Zoom into slides like Google Maps!"}
