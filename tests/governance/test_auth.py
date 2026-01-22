"""Unit Tests for RBAC Auth - Coverage for get_current_user, check_role

Self-Explanatory: Pytest with mocks for JWT/DB.
Why: Ensure dynamic RBAC works, no regressions.
How: Mock JWT decode, DB queries; test permissions.
Run: pytest tests/governance/
"""
import pytest
from fastapi import HTTPException
from src.governance.auth import get_current_user, check_role
from starlette.requests import Request
from jose import jwt
from unittest.mock import patch, AsyncMock

@pytest.mark.asyncio
async def test_get_current_user_valid(mocker):
    # Mock Request with valid JWT header
    request = mocker.Mock(spec=Request)
    request.headers = {'Authorization': 'Bearer valid.jwt.token'}
    
    # Mock jwt.decode
    with patch('jose.jwt.decode') as mock_decode:
        mock_decode.return_value = {'sub': 'test_user', 'role': 'pathologist'}
        
        user = await get_current_user(request)
        assert user['user_id'] == 'test_user'
        assert user['role'] == 'pathologist'

@pytest.mark.asyncio
async def test_get_current_user_invalid(mocker):
    request = mocker.Mock(spec=Request)
    request.headers = {'Authorization': 'Bearer invalid'}
    
    with pytest.raises(HTTPException) as exc:
        await get_current_user(request)
    assert exc.value.status_code == 401

@pytest.mark.asyncio
async def test_check_role_allowed(mocker):
    # Mock user
    user = {'user_id': 'test_user'}
    
    # Mock DB query
    mock_conn = mocker.Mock()
    mock_conn.execute.return_value.fetchall.return_value = [[{'upload': True}]]
    with patch('src.governance.auth.engine.connect') as mock_connect:
        mock_connect.return_value.__enter__.return_value = mock_conn
        
        checker = check_role("upload")
        result = await checker(user)
        assert result == user

@pytest.mark.asyncio
async def test_check_role_denied(mocker):
    user = {'user_id': 'test_user'}
    mock_conn = mocker.Mock()
    mock_conn.execute.return_value.fetchall.return_value = [[]]  # No perms
    with patch('src.governance.auth.engine.connect') as mock_connect:
        mock_connect.return_value.__enter__.return_value = mock_conn
        
        checker = check_role("upload")
        with pytest.raises(HTTPException) as exc:
            await checker(user)
    assert exc.value.status_code == 403

# More tests: No user, wildcard '*', multiple roles
@pytest.mark.asyncio
async def test_check_role_wildcard(mocker):
    user = {'user_id': 'admin'}
    mock_conn = mocker.Mock()
    mock_conn.execute.return_value.fetchall.return_value = [[{'*': True}]]
    with patch('src.governance.auth.engine.connect') as mock_connect:
        mock_connect.return_value.__enter__.return_value = mock_conn
        
        checker = check_role("any_endpoint")
        result = await checker(user)
        assert result == user
