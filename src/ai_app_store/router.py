"""AI App Store Router - Run AI apps (triage, heatmaps, etc.)

Endpoints:
- /apps: List available AI apps
- /run/triage/{slide_id}: Run triage (batch/realtime)
- /run/heatmap/{slide_id}/{level}/{x}/{y}: Get heatmap overlay tile
Why: Modular AI - extend with more apps (Ki-67, etc.)
How: Integrates IMS/viewer; signed outputs.
GPU Queue: Demo sync (prod: async queue).
"""

from fastapi import APIRouter, HTTPException, Response, Depends
import structlog
from src.utils.ai_utils import run_triage, generate_heatmap, sign_inference
from src.governance.auth import check_role
from typing import List, Dict

router = APIRouter()
logger = structlog.get_logger()

@router.get("/apps", response_model=List[Dict[str, str]])
async def list_apps(user: Dict[str, str] = Depends(check_role("list"))):  # Reuse list role
    """List available AI apps"""
    apps = [
        {"name": "triage", "description": "Normal vs Suspicious classification"},
        {"name": "heatmap", "description": "Tumor hotspot heatmaps"}
        # Add more: ki67, her2, etc.
    ]
    logger.info("AI apps listed", user_id=user["user_id"])
    return apps

@router.get("/run/triage/{slide_id}")
async def run_triage_app(slide_id: str, user: Dict[str, str] = Depends(check_role("ai_run"))):
    """Run triage AI on slide"""
    result = run_triage(slide_id)
    signature = sign_inference(result)
    result["signature"] = signature
    logger.info("Triage executed", slide_id=slide_id, user_id=user["user_id"])
    return result

@router.get("/run/heatmap/{slide_id}/{level}/{x}/{y}")
async def run_heatmap_app(slide_id: str, level: int, x: int, y: int, user: Dict[str, str] = Depends(check_role("ai_run"))):
    """Get heatmap overlay for tile"""
    heatmap_bytes = generate_heatmap(slide_id, level, x, y)
    logger.info("Heatmap executed", slide_id=slide_id, level=level, x=x, y=y, user_id=user["user_id"])
    return Response(content=heatmap_bytes, media_type="image/png")

@router.get("/")
async def ai_home():
    return {"message": "PATHAI AI Store - Run apps! Use /apps, /run/triage/{id}, /run/heatmap/{id}/{level}/{x}/{y}"}
