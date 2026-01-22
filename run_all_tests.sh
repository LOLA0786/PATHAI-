#!/bin/bash
# PATHAI Full Test Runner - Unit/Integration (Mumbai debug mode)
set -e  # Exit on error

# Setup (DB mock if not real)
export TEST_DB_URL="sqlite:///:memory:"  # For CI; use real for local
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Run unit tests (auth/RBAC)
pytest tests/governance/test_auth.py -v

# Run integration (audit/HL7)
pytest tests/governance/test_audit_integration.py -v

# Manual API tests (curl; assume server running: python src/main.py)
echo "Manual IMS Upload Test (expect 200, check logs/DB for audit)"
curl -X POST "http://localhost:8000/ims/upload" -F "file=@/path/to/test.svs" -H "Authorization: Bearer eyJ1c2VyX2lkIjoidGVzdCIsInJvbGUiOiJwYXRob2xvZ2lzdCJ9"

echo "Manual HL7 Receive Test (expect 200, signed log)"
curl -X POST "http://localhost:8000/hl7/receive" -d "MSH|^~\&|TEST|FAC|PATHAI|FAC|20260122||ORM^O01|123|P|2.5"

echo "Check DB logs (psql): SELECT * FROM audit_logs;"

# AI async test (run task, poll result)
curl "http://localhost:8000/ai/run/triage/test_slide_id" -H "Authorization: Bearer base64_token"
# Poll task_id from response

# Viewer tile test
curl "http://localhost:8000/viewer/tile/test_slide_id/0/0/0" --output tile.png

# Cleanup
deactivate
rm -rf venv
