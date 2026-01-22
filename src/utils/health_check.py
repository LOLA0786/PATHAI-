"""Enhanced Health Check - Production-Grade Service Health

Self-Explanatory: Comprehensive health checks for all dependencies.
Why: Current /health only returns static JSON; need real dependency checks.
How: Check DB, Redis, S3, Celery, KMS; return detailed status.

K8s Integration:
- /health/live: Liveness probe (is service running?)
- /health/ready: Readiness probe (can serve traffic?)
- /health/startup: Startup probe (finished initialization?)
"""

import time
from datetime import datetime
from typing import Dict, List

import structlog
from fastapi import status
from fastapi.responses import JSONResponse

logger = structlog.get_logger()


class HealthStatus:
    """Health status constants"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


class HealthChecker:
    """Comprehensive health check for all system dependencies"""

    def __init__(self):
        self.start_time = time.time()
        logger.info("Health checker initialized")

    async def check_database(self) -> Dict:
        """Check PostgreSQL database connectivity"""
        try:
            from src.governance.audit_logger import engine
            from sqlalchemy import text

            with engine.connect() as conn:
                start = time.time()
                conn.execute(text("SELECT 1"))
                latency_ms = (time.time() - start) * 1000

            return {
                "status": HealthStatus.HEALTHY,
                "latency_ms": round(latency_ms, 2),
                "message": "Database connection successful"
            }

        except Exception as e:
            logger.error("Database health check failed", error=str(e))
            return {
                "status": HealthStatus.UNHEALTHY,
                "error": str(e),
                "message": "Database connection failed"
            }

    async def check_redis(self) -> Dict:
        """Check Redis connectivity"""
        try:
            from src.viewer.tile_cache import r

            start = time.time()
            r.ping()
            latency_ms = (time.time() - start) * 1000

            # Get info
            info = r.info()
            used_memory_mb = info.get("used_memory", 0) / 1024 / 1024

            return {
                "status": HealthStatus.HEALTHY,
                "latency_ms": round(latency_ms, 2),
                "used_memory_mb": round(used_memory_mb, 2),
                "message": "Redis connection successful"
            }

        except Exception as e:
            logger.error("Redis health check failed", error=str(e))
            return {
                "status": HealthStatus.UNHEALTHY,
                "error": str(e),
                "message": "Redis connection failed"
            }

    async def check_s3(self) -> Dict:
        """Check S3 connectivity (optional for local dev)"""
        try:
            import boto3
            from botocore.exceptions import ClientError

            s3_client = boto3.client("s3", region_name="ap-south-1")

            start = time.time()
            # Try to list buckets (lightweight operation)
            s3_client.list_buckets()
            latency_ms = (time.time() - start) * 1000

            return {
                "status": HealthStatus.HEALTHY,
                "latency_ms": round(latency_ms, 2),
                "message": "S3 connection successful"
            }

        except Exception as e:
            logger.warning("S3 health check failed (optional)", error=str(e))
            return {
                "status": HealthStatus.DEGRADED,
                "error": str(e),
                "message": "S3 not configured (using local storage)"
            }

    async def check_celery(self) -> Dict:
        """Check Celery worker availability"""
        try:
            from src.ai_app_store.celery_app import app as celery_app

            # Check active workers
            inspect = celery_app.control.inspect()
            active_workers = inspect.active()

            if active_workers:
                worker_count = len(active_workers)
                total_tasks = sum(len(tasks) for tasks in active_workers.values())

                return {
                    "status": HealthStatus.HEALTHY,
                    "worker_count": worker_count,
                    "active_tasks": total_tasks,
                    "message": f"{worker_count} Celery workers active"
                }
            else:
                return {
                    "status": HealthStatus.DEGRADED,
                    "worker_count": 0,
                    "message": "No Celery workers found (AI features unavailable)"
                }

        except Exception as e:
            logger.error("Celery health check failed", error=str(e))
            return {
                "status": HealthStatus.UNHEALTHY,
                "error": str(e),
                "message": "Celery connection failed"
            }

    async def check_kms(self) -> Dict:
        """Check AWS KMS availability"""
        try:
            from src.security.kms_manager import kms_manager

            metadata = kms_manager.get_key_metadata()

            if "error" in metadata:
                return {
                    "status": HealthStatus.DEGRADED,
                    "message": "KMS not configured (using local encryption)",
                    "details": metadata
                }

            return {
                "status": HealthStatus.HEALTHY,
                "rotation_enabled": metadata.get("rotation_enabled", False),
                "message": "KMS connection successful"
            }

        except Exception as e:
            logger.warning("KMS health check failed", error=str(e))
            return {
                "status": HealthStatus.DEGRADED,
                "error": str(e),
                "message": "KMS not configured (using local encryption)"
            }

    async def check_disk_space(self) -> Dict:
        """Check local disk space"""
        try:
            import shutil

            usage = shutil.disk_usage("./data")
            free_gb = usage.free / (1024 ** 3)
            total_gb = usage.total / (1024 ** 3)
            used_percent = (usage.used / usage.total) * 100

            if used_percent > 90:
                status_val = HealthStatus.UNHEALTHY
                message = "Disk space critically low"
            elif used_percent > 80:
                status_val = HealthStatus.DEGRADED
                message = "Disk space running low"
            else:
                status_val = HealthStatus.HEALTHY
                message = "Disk space sufficient"

            return {
                "status": status_val,
                "free_gb": round(free_gb, 2),
                "total_gb": round(total_gb, 2),
                "used_percent": round(used_percent, 2),
                "message": message
            }

        except Exception as e:
            logger.error("Disk space check failed", error=str(e))
            return {
                "status": HealthStatus.DEGRADED,
                "error": str(e),
                "message": "Disk space check failed"
            }

    async def liveness_check(self) -> JSONResponse:
        """Kubernetes liveness probe

        Returns:
            200 if service is running (always healthy unless crashed)
        """
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "status": "alive",
                "timestamp": datetime.utcnow().isoformat(),
                "uptime_seconds": int(time.time() - self.start_time)
            }
        )

    async def readiness_check(self) -> JSONResponse:
        """Kubernetes readiness probe

        Returns:
            200 if service can handle traffic, 503 if not ready
        """
        # Check critical dependencies
        db_status = await self.check_database()
        redis_status = await self.check_redis()

        # Service is ready if DB and Redis are healthy
        is_ready = (
            db_status["status"] == HealthStatus.HEALTHY and
            redis_status["status"] == HealthStatus.HEALTHY
        )

        if is_ready:
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content={
                    "status": "ready",
                    "timestamp": datetime.utcnow().isoformat(),
                    "checks": {
                        "database": db_status,
                        "redis": redis_status
                    }
                }
            )
        else:
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={
                    "status": "not_ready",
                    "timestamp": datetime.utcnow().isoformat(),
                    "checks": {
                        "database": db_status,
                        "redis": redis_status
                    }
                }
            )

    async def comprehensive_check(self) -> Dict:
        """Full health check of all components

        Returns:
            Detailed status of all system components
        """
        checks = {
            "database": await self.check_database(),
            "redis": await self.check_redis(),
            "s3": await self.check_s3(),
            "celery": await self.check_celery(),
            "kms": await self.check_kms(),
            "disk": await self.check_disk_space(),
        }

        # Determine overall status
        unhealthy_count = sum(
            1 for check in checks.values()
            if check["status"] == HealthStatus.UNHEALTHY
        )
        degraded_count = sum(
            1 for check in checks.values()
            if check["status"] == HealthStatus.DEGRADED
        )

        if unhealthy_count > 0:
            overall_status = HealthStatus.UNHEALTHY
        elif degraded_count > 0:
            overall_status = HealthStatus.DEGRADED
        else:
            overall_status = HealthStatus.HEALTHY

        return {
            "status": overall_status,
            "timestamp": datetime.utcnow().isoformat(),
            "uptime_seconds": int(time.time() - self.start_time),
            "version": "1.0.0",
            "checks": checks,
            "summary": {
                "healthy": sum(
                    1 for c in checks.values()
                    if c["status"] == HealthStatus.HEALTHY
                ),
                "degraded": degraded_count,
                "unhealthy": unhealthy_count,
                "total": len(checks)
            }
        }


# Global instance
health_checker = HealthChecker()
