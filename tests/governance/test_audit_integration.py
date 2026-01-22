"""Integration Tests for Audit Logging - End-to-End Flows

Self-Explanatory: Pytest with TestClient, DB mocks.
Why: Ensure logs trigger on actions, immutable/signed.
How: Simulate upload/erase, query audit_logs table.
Run: pytest tests/governance/ -v
"""
import pytest
from fastapi.testclient import TestClient
from src.main import app
from sqlalchemy import create_engine, text
from unittest.mock import patch
import structlog

client = TestClient(app)
ENGINE_URL = 'postgresql://admin:securepass@pathai-db:5432/pathai'  # Test DB (use in-memory SQLite for CI)

@pytest.fixture
def mock_db():
    engine = create_engine(ENGINE_URL)
    with engine.connect() as conn:
        conn.execute(text("TRUNCATE audit_logs"))  # Clear for test
    yield engine
    # Teardown if needed

@pytest.mark.asyncio
async def test_audit_on_upload(mock_db, mocker):
    # Mock auth/user
    mocker.patch('src.governance.auth.get_current_user', return_value={'user_id': 'test_user', 'role': 'pathologist'})
    
    # Simulate upload (mock file/validate)
    with patch('src.ims.router.validate_slide') as mock_val,          patch('src.ims.router.de_identify_slide') as mock_deid,          patch('src.ims.router.encrypt_data') as mock_enc,          patch('src.ims.router.save_metadata') as mock_save:
        mock_val.return_value = mocker.Mock()  # Fake slide
        mock_deid.return_value = b'data'
        mock_enc.return_value = b'enc_data'
        
        response = client.post("/ims/upload", files={"file": ("test.svs", b"fake_content")})
        assert response.status_code == 200
    
    # Check audit log
    with mock_db.connect() as conn:
        logs = conn.execute(text("SELECT * FROM audit_logs WHERE user_id = 'test_user' AND action = 'upload'")).fetchall()
        assert len(logs) == 1
        log = logs[0]
        assert 'signature' in log  # Namedtuple, access by name/index
        assert log.details is not None  # JSONB with why/details

@pytest.mark.asyncio
async def test_audit_on_erase(mock_db, mocker):
    mocker.patch('src.governance.auth.get_current_user', return_value={'user_id': 'admin_user', 'role': 'admin'})
    
    response = client.post("/erase/test_patient_id")
    assert response.status_code == 200
    
    with mock_db.connect() as conn:
        logs = conn.execute(text("SELECT * FROM audit_logs WHERE action = 'erase'")).fetchall()
        assert len(logs) == 1
        assert 'PHI' not in str(logs[0].details)  # No leaked PHI

# More: Test immutability (try UPDATE, fail), signature verify
async def test_log_immutable(mock_db):
    # Insert test log
    with mock_db.connect() as conn:
        conn.execute(text("INSERT INTO audit_logs (user_id, action) VALUES ('test', 'test')"))
    
    # Attempt update (should fail if triggers/constraints; or test no change)
    with pytest.raises(Exception):  # Assume DB trigger prevents
        with mock_db.connect() as conn:
            conn.execute(text("UPDATE audit_logs SET action = 'hacked' WHERE user_id = 'test'"))

# Signature verify: In test, call hmac.verify on log

@pytest.mark.asyncio
async def test_audit_on_hl7_receive(mock_db, mocker):
    mocker.patch('src.governance.auth.get_current_user', return_value={'user_id': 'lis_user', 'role': 'pathologist'})
    
    hl7_sample = "MSH|^~\&|LIS|FAC|PATHAI|FAC|20260122||ORM^O01|12345|P|2.5"
    response = client.post("/hl7/receive", data=hl7_sample)
    assert response.status_code == 200
    
    with mock_db.connect() as conn:
        logs = conn.execute(text("SELECT * FROM audit_logs WHERE action = 'hl7_receive'")).fetchall()
        assert len(logs) == 1
        assert logs[0].signature is not None

# Similar for send_hl7 (mock httpx)
