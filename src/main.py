"""PATHAI Main FastAPI App - The Brain of the System

This file starts the entire server.
Run with: uvicorn src.main:app --reload
Access at: http://localhost:8000/docs (interactive docs!)
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import structlog  # For nice, traceable logs

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
    title="PATHAI - India's Digital Pathology Control Plane",
    description="Secure, AI-powered digital pathology platform",
    version="0.1.0",
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

# Import and include routers (mini-apps) from modules
from src.viewer.router import router as viewer_router
from src.ims.router import router as ims_router
from src.ai_app_store.router import router as ai_router
from src.governance.router import router as gov_router

app.include_router(viewer_router, prefix="/viewer", tags=["Viewer"])
app.include_router(ims_router, prefix="/ims", tags=["IMS"])
app.include_router(ai_router, prefix="/ai", tags=["AI App Store"])
app.include_router(gov_router, prefix="/governance", tags=["Governance"])

# Basic health check - like "Hello, I'm alive!"
@app.get("/health")
async def health_check():
    logger.info("Health check requested")
    return {"status": "healthy", "version": app.version}

if __name__ == "__main__":
    logger.info("Starting PATHAI server...")
    uvicorn.run("src.main:app", host="0.0.0.0", port=8000, reload=True)

from fastapi_socketio import SocketManager
sio = SocketManager(app=app)  # For tele-review WS
