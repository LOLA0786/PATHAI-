#!/bin/bash
# PATHAI Full Test Runner - Fixed for Mac/python3 (Mumbai debug)
set -e

# Setup (DB mock if not real)
export TEST_DB_URL="sqlite:///:memory:"

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Run unit tests (auth/RBAC)
pytest tests/governance/test_auth.py -v

# Run integration (audit/HL7)
pytest tests/governance/test_audit_integration.py -v

# Manual API tests (start server first if not: python3 src/main.py &)
echo "Manual IMS Upload (expect 200, check logs/DB)"
curl -X POST "http://localhost:8000/ims/upload" -F "file=@/path/to/test.svs" -H "Authorization: Bearer $(echo -n '{\"user_id\":\"test\",\"role\":\"pathologist\"}' | base64)"

echo "Manual HL7 Receive (expect 200, signed log)"
curl -X POST "http://localhost:8000/hl7/receive" -d "MSH|^~\&|TEST|FAC|PATHAI|FAC|20260122||ORM^O01|123|P|2.5"

echo "Check DB logs (psql or sqlite3): SELECT * FROM audit_logs;"

# AI test (triage)
curl "http://localhost:8000/ai/run/triage/test_slide_id" -H "Authorization: Bearer base64_token"

# Viewer tile
curl "http://localhost:8000/viewer/tile/test_slide_id/0/0/0" --output tile.png

# Cleanup
deactivate
rm -rf venv
kill %1  # Stop server if backgrounded
