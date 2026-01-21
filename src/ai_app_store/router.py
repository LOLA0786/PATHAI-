"""AI App Store Router - Run AI models on slides"""

from fastapi import APIRouter

router = APIRouter()

@router.get("/")
async def ai_home():
    return {"message": "PATHAI AI Store - Pick an AI app to run!"}
