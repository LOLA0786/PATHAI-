"""AI App Store Router - Async AI apps (triage, ki67, heatmaps)

Endpoints:
- /apps: List apps
- /run/triage/{slide_id}: Trigger async triage, return task_id
- /run/ki67/{slide_id}: Trigger async Ki-67 quant (optional level/x/y)
- /run/heatmap/{slide_id}/{level}/{x}/{y}: Sync heatmap (fast)
- /result/{task_id}: Get async result (poll)
"""
from fastapi import APIRouter, HTTPException, Response, Depends
import structlog
from src.utils.ai_utils import generate_heatmap, sign_inference
from src.governance.auth import check_role
from src.ai_app_store.tasks import async_triage, async_ki67_quant
from typing import List, Dict
from celery.result import AsyncResult

router = APIRouter()
logger = structlog.get_logger()

@router.get("/apps", response_model=List[Dict[str, str]])
async def list_apps(user: Dict[str, str] = Depends(check_role("list"))):
    apps = [
        {"name": "triage", "description": "Normal vs Suspicious"},
        {"name": "heatmap", "description": "Tumor heatmaps"},
        {"name": "ki67", "description": "Ki-67 quantification"}
    ]
    return apps

@router.get("/run/triage/{slide_id}")
async def run_triage_app(slide_id: str, user: Dict[str, str] = Depends(check_role("ai_run"))):
    task = async_triage.delay(slide_id)
    logger.info("Triage tasked", slide_id=slide_id, task_id=task.id, user_id=user["user_id"])
    return {"task_id": task.id, "status": "queued"}

@router.get("/run/ki67/{slide_id}")
async def run_ki67_app(slide_id: str, level: int = 0, x: int = 0, y: int = 0, user: Dict[str, str] = Depends(check_role("ai_run"))):
    task = async_ki67_quant.delay(slide_id, level, x, y)
    logger.info("Ki-67 tasked", slide_id=slide_id, task_id=task.id, user_id=user["user_id"])
    return {"task_id": task.id, "status": "queued"}

@router.get("/run/heatmap/{slide_id}/{level}/{x}/{y}")
async def run_heatmap_app(slide_id: str, level: int, x: int, y: int, user: Dict[str, str] = Depends(check_role("ai_run"))):
    heatmap_bytes = generate_heatmap(slide_id, level, x, y)
    return Response(content=heatmap_bytes, media_type="image/png")

@router.get("/result/{task_id}")
async def get_task_result(task_id: str, user: Dict[str, str] = Depends(check_role("ai_run"))):
    result = AsyncResult(task_id)
    if result.ready():
        return {"status": "done", "result": result.get()}
    elif result.failed():
        return {"status": "failed", "error": str(result.info)}
    else:
        return {"status": "pending"}

@router.get("/")
async def ai_home():
    return {"message": "PATHAI AI Store - Async apps! Trigger /run/*, poll /result/{id}"}
