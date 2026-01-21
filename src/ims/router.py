"""IMS Router - Image Management System (upload & store slides)"""

from fastapi import APIRouter

router = APIRouter()

@router.get("/")
async def ims_home():
    return {"message": "PATHAI IMS - Your secure slide storage!"}
