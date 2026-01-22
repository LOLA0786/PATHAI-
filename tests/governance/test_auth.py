"""Unit Tests for RBAC Auth - Coverage for get_current_user, check_role

Self-Explanatory: Pytest with mocks for JWT/DB.
Why: Ensure dynamic role works, no regressions.
How: Mock JWT decode, DB queries; test permissions.
Run: pytest tests/governance/
"""
import pytest
from fastapi import HTTPException
from src.governance.auth import get_current_user, check_role
from unittest.mock import patch, MagicMock
import base64
import asyncio

@pytest.fixture
def event_loop():
    loop = asyncio.get_event_loop()
    yield loop
    loop.close()

def test_get_current_user_valid():
    # Valid base64 token (encoded {'user_id': 'test_user', 'role': 'pathologist'})
    encoded = base64.b64encode(b'{"user_id": "test_user", "role": "pathologist"}').decode()
    authorization = f'Bearer {encoded}'
    
    user = get_current_user(authorization=authorization)
    assert user['user_id'] == 'test_user'
    assert user['role'] == 'pathologist'

def test_get_current_user_invalid():
    with pytest.raises(HTTPException) as exc:
        get_current_user(authorization=None)
    assert exc.value.status_code == 401

@pytest.mark.asyncio
async def test_check_role_allowed():
    user = {'user_id': 'test_user', 'role': 'pathologist'}
    
    checker = check_role("upload")
    result = await checker(user)
    assert result == user

@pytest.mark.asyncio
async def test_check_role_denied():
    user = {'user_id': 'test_user', 'role': 'viewer'}
    
    checker = check_role("upload")
    with pytest.raises(HTTPException) as exc:
        await checker(user)
    assert exc.value.status_code == 403

@pytest.mark.asyncio
async def test_check_role_wildcard():
    user = {'user_id': 'admin', 'role': 'admin'}
    
    checker = check_role("delete")  # Known endpoint for admin
    result = await checker(user)
    assert result == user
