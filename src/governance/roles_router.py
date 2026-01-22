"""Roles Router - Admin manage RBAC

Endpoints: /roles (list/create/update/delete)
RBAC: Admin only.
"""
from fastapi import APIRouter, Depends, HTTPException
from src.governance.auth import check_role
from pydantic import BaseModel
from sqlalchemy import text
import structlog

router = APIRouter(prefix="/roles", tags=["RBAC"])
logger = structlog.get_logger()

class Role(BaseModel):
    name: str
    permissions: dict

@router.get("/")
async def list_roles(user: dict = Depends(check_role("*"))):  # Admin wild
    with engine.connect() as conn:
        roles = conn.execute(text("SELECT name, permissions FROM roles")).fetchall()
    return [ {"name": r[0], "permissions": r[1]} for r in roles ]

@router.post("/")
async def create_role(role: Role, user: dict = Depends(check_role("*"))):
    with engine.connect() as conn:
        conn.execute(text("INSERT INTO roles (name, permissions) VALUES (:n, :p)"),
                     {"n": role.name, "p": role.permissions})
    logger.info("Role created", name=role.name)
    return {"status": "created"}

# Similar for update/delete, assign to users: /assign/{user_id}/{role_name}
