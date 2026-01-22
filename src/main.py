"""PATHAI Main FastAPI App - The Brain of the System (BEAST MODE)

This file starts the entire server with all production-grade features.
Run with: uvicorn src.main:app --reload
Access at: http://localhost:8000/docs (interactive docs!)

NEW BEAST FEATURES:
1. Offline-First Sync: Chunked uploads with auto-resume for rural labs
2. AWS KMS: Enterprise key management with automatic rotation
3. Observability: Prometheus metrics + enhanced health checks
4. ABHA Integration: Ayushman Bharat Digital Health integration
5. Multi-Language: AI annotations in 10 Indian languages
6. Screening Campaigns: TB & Cancer mass screening workflows
7. Blockchain Audit: Immutable audit trail with blockchain anchoring
"""

from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
import uvicorn
import structlog  # For nice, traceable logs
import asyncio

# Set up structured logging (easy to read later)
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.stdlib.add_log_level,
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()

# Create the main app
app = FastAPI(
    title="PATHAI - India's Digital Pathology Control Plane (BEAST MODE)",
    description="""
    **Production-Grade Features:**
    - 🌐 Offline-First Sync for rural labs (2G/3G support)
    - 🔐 AWS KMS encryption with automatic key rotation
    - 📊 Prometheus metrics + comprehensive observability
    - 🏥 ABHA (Ayushman Bharat) integration
    - 🗣️ Multi-language AI (10 Indian languages)
    - 🎗️ TB/Cancer screening campaigns
    - ⛓️ Blockchain-backed immutable audit trail
    """,
    version="1.0.0-BEAST",
    docs_url="/docs",  # Swagger UI
    redoc_url="/redoc",
)

# Allow frontend (web viewer) to connect from anywhere (for now)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Change to your domains later
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================================
# IMPORT ROUTERS - Core + New Beast Features
# ============================================================================

# Core modules
from src.viewer.router import router as viewer_router
from src.ims.router import router as ims_router
from src.ai_app_store.router import router as ai_router
from src.governance.router import router as gov_router

# NEW: Beast feature routers
from src.sync.router import router as sync_router
from src.integrations.abha.router import router as abha_router
from src.integrations.hl7_adapter import router as hl7_router

# Mount routers
app.include_router(viewer_router, prefix="/viewer", tags=["Viewer"])
app.include_router(ims_router, prefix="/ims", tags=["IMS"])
app.include_router(ai_router, prefix="/ai", tags=["AI App Store"])
app.include_router(gov_router, prefix="/governance", tags=["Governance"])

# NEW: Beast features
app.include_router(sync_router, prefix="/sync", tags=["Offline Sync"])
app.include_router(abha_router, prefix="/abha", tags=["ABHA Integration"])
app.include_router(hl7_router, prefix="/hl7", tags=["LIS/HIS Integration"])

# ============================================================================
# HEALTH CHECKS - Production-Grade
# ============================================================================

from src.utils.health_check import health_checker

@app.get("/health")
async def health_check():
    """Basic liveness check"""
    return await health_checker.liveness_check()

@app.get("/health/live")
async def health_live():
    """Kubernetes liveness probe"""
    return await health_checker.liveness_check()

@app.get("/health/ready")
async def health_ready():
    """Kubernetes readiness probe"""
    return await health_checker.readiness_check()

@app.get("/health/comprehensive")
async def health_comprehensive():
    """Comprehensive health check of all components"""
    return await health_checker.comprehensive_check()

# ============================================================================
# PROMETHEUS METRICS
# ============================================================================

from src.utils.metrics import get_metrics_text

@app.get("/metrics", response_class=PlainTextResponse)
async def metrics():
    """Prometheus metrics endpoint"""
    return get_metrics_text()

# ============================================================================
# STARTUP/SHUTDOWN EVENTS
# ============================================================================

@app.on_event("startup")
async def startup_event():
    """Initialize services on startup"""
    logger.info("=" * 80)
    logger.info("🚀 PATHAI BEAST MODE STARTING")
    logger.info("=" * 80)

    # Initialize KMS
    from src.security.kms_manager import kms_manager
    kms_status = kms_manager.get_key_metadata()
    logger.info("KMS initialized", status=kms_status.get("key_state", "fallback"))

    # Start offline sync worker (background)
    from src.sync.offline_manager import sync_manager
    asyncio.create_task(sync_manager.sync_worker())
    logger.info("Offline sync worker started")

    # Initialize ABHA client
    from src.integrations.abha.abha_client import abha_client
    logger.info("ABHA client initialized")

    # Initialize blockchain audit logger
    from src.governance.blockchain_audit import blockchain_audit_logger
    logger.info("Blockchain audit logger initialized")

    # Initialize screening campaign manager
    from src.workflows.screening.campaign_manager import campaign_manager
    logger.info("Screening campaign manager initialized")

    logger.info("=" * 80)
    logger.info("✅ PATHAI BEAST MODE READY")
    logger.info("📊 Metrics: http://localhost:8000/metrics")
    logger.info("📚 Docs: http://localhost:8000/docs")
    logger.info("=" * 80)

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    logger.info("Shutting down PATHAI...")

    # Anchor any pending audit logs
    from src.governance.blockchain_audit import blockchain_audit_logger
    await blockchain_audit_logger.anchor_to_blockchain()
    logger.info("Final blockchain anchor completed")

# ============================================================================
# WEBSOCKET FOR TELE-PATHOLOGY
# ============================================================================

from fastapi_socketio import SocketManager
sio = SocketManager(app=app)  # For tele-review WS

# ============================================================================
# MIDDLEWARE
# ============================================================================

from src.governance.deid_middleware import DeIDMiddleware
app.add_middleware(DeIDMiddleware)

# ============================================================================
# ROOT ENDPOINT
# ============================================================================

@app.get("/")
async def root():
    """Root endpoint with system info"""
    return {
        "message": "PATHAI - India's Digital Pathology Control Plane (BEAST MODE)",
        "version": "1.0.0-BEAST",
        "features": {
            "offline_sync": "✅ Enabled",
            "kms_encryption": "✅ Enabled",
            "prometheus_metrics": "✅ Enabled",
            "abha_integration": "✅ Enabled",
            "multi_language": "✅ 10 languages",
            "screening_campaigns": "✅ TB & Cancer",
            "blockchain_audit": "✅ Enabled"
        },
        "docs": "/docs",
        "metrics": "/metrics",
        "health": "/health/comprehensive"
    }

# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    logger.info("Starting PATHAI BEAST MODE server...")
    uvicorn.run("src.main:app", host="0.0.0.0", port=8000, reload=True)
