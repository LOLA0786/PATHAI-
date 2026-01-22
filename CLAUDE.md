# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

PATHAI is India's Digital Pathology Control Plane: a software-first platform for massive-scale digital pathology. It combines hybrid cloud+edge architecture with offline-first design for rural labs, focusing on WSI Viewer, Image Management System (IMS/PACS), AI App Store, and strong governance/compliance features.

## Core Architecture

**Modular Design**: Each module in `src/` is self-contained with its own router, utilities, and domain logic. The system uses FastAPI with structured logging (structlog) and is designed for hybrid cloud (AWS/GCP/Azure) and edge (Docker/K8s) deployment.

**Main Components**:
- `src/main.py`: FastAPI app entrypoint that mounts all module routers
- `src/viewer/`: Tile-based WSI viewer using OpenSlide with tele-review (WebSocket annotations)
- `src/ims/`: Image Management System for SVS/NDPI/MRXS ingestion, storage, retrieval
- `src/ai_app_store/`: GPU-powered AI applications (triage, Ki-67, HER2, PD-L1, TILs, mitosis detection, etc.) with Celery async processing
- `src/governance/`: RBAC authentication, de-identification, audit logging, OAuth/OIDC support, DPDP compliance
- `src/integrations/`: HL7 v2.x adapter for LIS/HIS bi-directional integration
- `src/utils/`: Shared utilities (slide handling, encryption, AI inference, stain normalization)

**Key Architectural Patterns**:
- All endpoints are RBAC-protected via dependency injection (`Depends(check_role(...))`)
- Audit logging is cryptographically signed and append-only for compliance (NABL/DPDP)
- PHI data is encrypted at rest using AES-256-GCM
- AI inference uses async task queues (Celery + Redis) for scalability
- WebSocket (socket.io) enables real-time tele-pathology collaboration

## Commands

### Development Setup
```bash
# Install dependencies
pip install -r requirements.txt

# Run the main server (with hot reload)
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

# Or run directly
python src.main.py
```

### Running Tests
```bash
# Run all tests with verbose output
pytest tests/ -v

# Run specific test module (e.g., auth tests)
pytest tests/governance/test_auth.py -v

# Run integration tests (requires DB)
pytest tests/governance/test_audit_integration.py -v

# Use the provided test script (sets up venv, runs all tests)
bash run_all_tests_fixed.sh
```

### Celery Worker (for AI async tasks)
```bash
# Start Celery worker for AI App Store
celery -A src.ai_app_store.celery_app worker --loglevel=info

# Requires Redis running locally or configured
# Default: redis://localhost:6379/0
```

### Database Setup
```bash
# Initialize database with schema (PostgreSQL)
psql -U admin -d pathai -f configs/db_schema.sql

# For tests, use in-memory SQLite:
export TEST_DB_URL="sqlite:///:memory:"
```

## Authentication & Authorization

**RBAC System**: Uses base64-encoded tokens (demo) or JWT (production-ready via `src/governance/oauth.py`).

**Token Format** (demo):
```bash
# Create a token: base64({"user_id": "user123", "role": "pathologist"})
echo '{"user_id":"test","role":"pathologist"}' | base64
# Use as: Authorization: Bearer <token>
```

**Roles & Permissions**:
- `admin`: Full access (upload, retrieve, list, metadata, delete, audit)
- `pathologist`: Read/write slides, run AI (upload, retrieve, list, metadata, ai_run)
- `viewer`: Read-only access (list, metadata)
- `researcher`: AI execution only (ai_run, list)
- `auditor`: Audit log access (list, metadata, audit)

**Important Functions** (in `src/governance/auth.py`):
- `get_current_user()`: Extracts user from Authorization header
- `check_role(endpoint)`: Dependency factory for endpoint protection

## Data Flow & Key Processes

### Slide Upload Flow
1. Upload via `/ims/upload` (RBAC: admin/pathologist)
2. Validate format (OpenSlide: SVS/NDPI/MRXS)
3. Extract metadata (dimensions, vendor info)
4. De-identify (scrub DICOM/labels via OCR)
5. Encrypt with AES-256-GCM
6. Store as `{slide_id}.enc` + `{slide_id}.json` metadata
7. Log to audit trail with HMAC signature

### AI Inference Flow
1. Trigger via `/ai/run/{app_name}/{slide_id}` (returns task_id)
2. Task queued to Celery (Redis broker)
3. Worker decrypts slide, runs PyTorch model
4. Result stored with signature
5. Poll `/ai/result/{task_id}` for completion
6. Annotations broadcast via WebSocket to tele-review session

### HL7 Integration Flow
1. Receive HL7 message at `/hl7/receive` (e.g., ORM order)
2. Parse with hl7apy, validate
3. Sign message with HMAC-SHA256
4. Log to audit trail
5. Process workflow (e.g., trigger slide upload)
6. Send ACK response
7. For outbound (ORU reports), call `send_hl7()` async

## Database Schema

Key tables (see `configs/db_schema.sql`):
- `patients`: PHI encrypted in JSONB, consent tokens
- `slides`: Links to patients, file paths, metadata
- `annotations`: User annotations with timestamps
- `ai_jobs`: Async AI task status/results with signatures
- `audit_logs`: Append-only, signed, TimescaleDB hypertable for time-series queries
- `roles` / `user_roles`: RBAC role definitions and assignments

## Configuration

**Environment Variables** (not in repo, set for deployment):
- `TEST_DB_URL`: Database URL for tests (default: SQLite in-memory)
- Database connection in `src/governance/audit_logger.py`: `postgresql://admin:securepass@pathai-db:5432/pathai`
- Redis broker in `src/ai_app_store/celery_app.py`: `redis://localhost:6379/0`
- Encryption key in `src/utils/slide_utils.py`: Uses hardcoded demo key (rotate for prod)

**AWS Deployment**: See `configs/aws_setup.sh` for Mumbai (ap-south-1) setup with DR in Singapore, including VPC, S3 (encrypted, Glacier lifecycle), RDS (Multi-AZ), ElastiCache Redis.

## API Documentation

Once server is running:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
- Health check: `http://localhost:8000/health`

**Module Endpoints**:
- IMS: `/ims/*` (upload, retrieve, list, metadata, delete)
- Viewer: `/viewer/*` (tile, info, annotations, WebSocket at `/ws/tele/{slide_id}`)
- AI: `/ai/*` (apps, run/{app}/{slide_id}, result/{task_id})
- Governance: `/governance/*` (roles, OAuth/OIDC)
- LIS: `/hl7/*` (receive, send)

## Code Style & Conventions

- All modules have extensive docstrings explaining Why/How/What
- Use structlog for all logging with structured context
- Dependency injection pattern for auth: `user: Dict = Depends(check_role("endpoint"))`
- Always log audit trail for sensitive operations
- Async/await for I/O operations (file uploads, HTTP requests)
- Type hints encouraged but not enforced
- Pydantic models for API request/response validation

## Testing Strategy

**Unit Tests**: Mock external dependencies (DB, file I/O, OpenSlide)
- Located in `tests/governance/`
- Use pytest fixtures for event loops
- Example: `test_auth.py` tests token validation and role checks

**Integration Tests**: Use FastAPI TestClient with DB
- Mock auth via `mocker.patch('src.governance.auth.get_current_user')`
- Verify audit log entries in database
- Example: `test_audit_integration.py` simulates full workflows

**Manual API Tests**: Provided in `run_all_tests.sh` using curl commands against running server

## Critical Security Notes

- Default encryption key in `src/utils/slide_utils.py` is for demo only; rotate in production using KMS
- Audit log signatures use HMAC-SHA256; ensure key rotation policy
- Base64 auth tokens are for development; use JWT with proper signing in production (`src/governance/oauth.py` has Authlib/python-jose setup)
- De-identification uses OCR (Tesseract) for labels but may need additional DICOM tag scrubbing depending on modality
- HL7 signing key in `src/integrations/hl7_adapter.py` is hardcoded; move to secure key management

## Troubleshooting

**Import Errors**: Ensure you run server from repo root with `uvicorn src.main:app` or `python src.main.py` (not from src/ directory)

**OpenSlide Not Found**: Install OpenSlide system library:
- Ubuntu: `apt-get install openslide-tools`
- macOS: `brew install openslide`

**Celery Worker Not Processing**: Check Redis is running (`redis-cli ping`) and worker logs for task routing issues

**WebSocket Connection Fails**: Ensure CORS middleware allows your frontend origin in `src/main.py`

**Database Connection Errors**: Update connection strings in `src/governance/audit_logger.py` and test files; for CI/testing use SQLite

## Future Extensions

- Production OAuth/OIDC integration (skeleton in `src/governance/oauth.py`)
- Dynamic policy engine for RBAC (integrate with UAAL repo patterns)
- Edge sync for offline labs (Docker/K8s deployment configs)
- Multi-region replication for disaster recovery
- FHIR integration alongside HL7 v2.x
