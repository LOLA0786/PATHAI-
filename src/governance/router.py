"""Governance Router - Security, de-ID, audits"""

from fastapi import APIRouter

router = APIRouter()

@router.get("/")
async def gov_home():
    return {"message": "PATHAI Governance - Everything secure & compliant!"}
