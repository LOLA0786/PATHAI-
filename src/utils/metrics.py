"""Prometheus Metrics - Comprehensive Observability for PATHAI

Self-Explanatory: Export custom metrics for monitoring at scale.
Why: Need real-time visibility into 10,000+ hospitals, millions of slides/day.
How: Prometheus client exports /metrics endpoint, Grafana visualizes.

Metrics Categories:
1. Business Metrics: slides_uploaded, ai_inferences_run, reports_generated
2. Performance Metrics: upload_duration, inference_latency, tile_latency
3. System Metrics: db_connections, redis_cache_hit_rate, celery_queue_depth
4. Compliance Metrics: audit_logs_written, consent_violations, encryption_failures

Dashboards:
- National Overview: Total slides by state, TAT by hospital
- Hospital View: Per-hospital throughput, SLA compliance
- Clinical View: Disease distribution, urgent case volume
- Technical View: System health, bottlenecks, errors
"""

import time
from functools import wraps
from typing import Callable

import structlog
from prometheus_client import (
    Counter,
    Gauge,
    Histogram,
    Info,
    generate_latest,
    REGISTRY,
    CollectorRegistry,
)

logger = structlog.get_logger()

# ============================================================================
# BUSINESS METRICS
# ============================================================================

# Slide Operations
slides_uploaded_total = Counter(
    "pathai_slides_uploaded_total",
    "Total slides uploaded to system",
    ["hospital_id", "state", "format", "priority"],
)

slides_processed_total = Counter(
    "pathai_slides_processed_total",
    "Total slides fully processed (encrypted, de-ID, stored)",
    ["hospital_id", "state"],
)

slides_failed_total = Counter(
    "pathai_slides_failed_total",
    "Total slides failed to process",
    ["hospital_id", "state", "error_type"],
)

# AI Inferences
ai_inferences_total = Counter(
    "pathai_ai_inferences_total",
    "Total AI inferences run",
    ["app_name", "hospital_id", "state"],
)

ai_inferences_by_disease = Counter(
    "pathai_ai_inferences_by_disease",
    "AI inferences by detected disease",
    ["disease", "severity", "state"],
)

# Reports
reports_generated_total = Counter(
    "pathai_reports_generated_total",
    "Total pathology reports generated",
    ["hospital_id", "state", "report_type"],
)

# Users
active_users_current = Gauge(
    "pathai_active_users_current",
    "Current number of active users",
    ["role", "hospital_id"],
)

# ============================================================================
# PERFORMANCE METRICS
# ============================================================================

# Upload Performance
upload_duration_seconds = Histogram(
    "pathai_upload_duration_seconds",
    "Time to upload and process slide",
    ["hospital_id", "file_size_category"],
    buckets=[10, 30, 60, 120, 300, 600, 1800],  # 10s to 30min
)

upload_size_bytes = Histogram(
    "pathai_upload_size_bytes",
    "Size of uploaded slides in bytes",
    ["format"],
    buckets=[
        50 * 1024 * 1024,  # 50 MB
        100 * 1024 * 1024,  # 100 MB
        250 * 1024 * 1024,  # 250 MB
        500 * 1024 * 1024,  # 500 MB
        1024 * 1024 * 1024,  # 1 GB
    ],
)

# AI Inference Performance
inference_duration_seconds = Histogram(
    "pathai_inference_duration_seconds",
    "AI inference latency",
    ["app_name", "model_version"],
    buckets=[0.5, 1, 2, 5, 10, 30, 60, 120],  # 0.5s to 2min
)

# Viewer Performance
tile_generation_duration_seconds = Histogram(
    "pathai_tile_generation_duration_seconds",
    "Time to generate WSI tile",
    ["level"],
    buckets=[0.01, 0.05, 0.1, 0.5, 1, 2],  # 10ms to 2s
)

tile_requests_total = Counter(
    "pathai_tile_requests_total",
    "Total tile requests from viewer",
    ["hospital_id", "cache_hit"],
)

# ============================================================================
# SYSTEM METRICS
# ============================================================================

# Database
db_connections_current = Gauge(
    "pathai_db_connections_current",
    "Current database connections",
)

db_query_duration_seconds = Histogram(
    "pathai_db_query_duration_seconds",
    "Database query latency",
    ["query_type"],
    buckets=[0.001, 0.01, 0.1, 0.5, 1, 5],
)

# Cache
redis_cache_hit_rate = Gauge(
    "pathai_redis_cache_hit_rate",
    "Redis cache hit rate (0-1)",
)

redis_cache_size_bytes = Gauge(
    "pathai_redis_cache_size_bytes",
    "Redis cache size in bytes",
)

# Celery Queue
celery_queue_depth = Gauge(
    "pathai_celery_queue_depth",
    "Number of tasks in Celery queue",
    ["queue_name"],
)

celery_task_duration_seconds = Histogram(
    "pathai_celery_task_duration_seconds",
    "Celery task execution time",
    ["task_name", "status"],
    buckets=[1, 5, 10, 30, 60, 300, 600],
)

# Storage
storage_used_bytes = Gauge(
    "pathai_storage_used_bytes",
    "Total storage used in bytes",
    ["storage_type"],  # local, s3, glacier
)

# ============================================================================
# COMPLIANCE METRICS
# ============================================================================

audit_logs_written_total = Counter(
    "pathai_audit_logs_written_total",
    "Total audit log entries written",
    ["action_type", "user_role"],
)

consent_checks_total = Counter(
    "pathai_consent_checks_total",
    "Total consent checks performed",
    ["result"],  # granted, denied, expired
)

encryption_operations_total = Counter(
    "pathai_encryption_operations_total",
    "Total encryption/decryption operations",
    ["operation", "algorithm"],
)

deid_operations_total = Counter(
    "pathai_deid_operations_total",
    "Total de-identification operations",
    ["method", "phi_detected"],
)

# ============================================================================
# INDIA-SPECIFIC METRICS
# ============================================================================

# Geographic Distribution
slides_by_state = Gauge(
    "pathai_slides_by_state",
    "Current slides in system by state",
    ["state"],
)

rural_vs_urban_slides = Counter(
    "pathai_rural_vs_urban_slides_total",
    "Slides from rural vs urban hospitals",
    ["location_type", "state"],
)

# National Health Programs
tb_screening_slides_total = Counter(
    "pathai_tb_screening_slides_total",
    "TB screening slides processed",
    ["state", "result"],  # positive, negative, suspicious
)

cancer_screening_slides_total = Counter(
    "pathai_cancer_screening_slides_total",
    "Cancer screening slides processed",
    ["cancer_type", "state", "result"],
)

# Turnaround Time (TAT)
tat_hours = Histogram(
    "pathai_turnaround_time_hours",
    "Time from upload to report (hours)",
    ["hospital_id", "urgency"],
    buckets=[1, 4, 8, 12, 24, 48, 72],  # 1h to 3 days
)

# ABHA Integration
abha_validations_total = Counter(
    "pathai_abha_validations_total",
    "ABHA number validations",
    ["result"],  # valid, invalid, api_error
)

# Offline Sync
offline_sync_queue_depth = Gauge(
    "pathai_offline_sync_queue_depth",
    "Number of slides waiting for sync",
    ["hospital_id", "priority"],
)

offline_sync_failures = Counter(
    "pathai_offline_sync_failures_total",
    "Failed offline sync attempts",
    ["hospital_id", "error_type"],
)

# ============================================================================
# SYSTEM INFO
# ============================================================================

system_info = Info(
    "pathai_system",
    "PATHAI system information",
)

system_info.info({
    "version": "1.0.0",
    "region": "ap-south-1",
    "environment": "production",
})

# ============================================================================
# DECORATOR UTILITIES
# ============================================================================


def track_upload_time(hospital_id: str, file_size_category: str):
    """Decorator to track upload duration"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = await func(*args, **kwargs)
                duration = time.time() - start_time
                upload_duration_seconds.labels(
                    hospital_id=hospital_id,
                    file_size_category=file_size_category
                ).observe(duration)
                return result
            except Exception as e:
                duration = time.time() - start_time
                upload_duration_seconds.labels(
                    hospital_id=hospital_id,
                    file_size_category=file_size_category
                ).observe(duration)
                raise
        return wrapper
    return decorator


def track_inference_time(app_name: str, model_version: str):
    """Decorator to track AI inference duration"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                duration = time.time() - start_time
                inference_duration_seconds.labels(
                    app_name=app_name,
                    model_version=model_version
                ).observe(duration)
                return result
            except Exception as e:
                duration = time.time() - start_time
                inference_duration_seconds.labels(
                    app_name=app_name,
                    model_version=model_version
                ).observe(duration)
                raise
        return wrapper
    return decorator


def track_db_query(query_type: str):
    """Decorator to track database query duration"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                duration = time.time() - start_time
                db_query_duration_seconds.labels(
                    query_type=query_type
                ).observe(duration)
                return result
            except Exception as e:
                duration = time.time() - start_time
                db_query_duration_seconds.labels(
                    query_type=query_type
                ).observe(duration)
                raise
        return wrapper
    return decorator


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def record_slide_upload(hospital_id: str, state: str, format: str, priority: str):
    """Record a slide upload"""
    slides_uploaded_total.labels(
        hospital_id=hospital_id,
        state=state,
        format=format,
        priority=priority
    ).inc()


def record_ai_inference(app_name: str, hospital_id: str, state: str):
    """Record an AI inference"""
    ai_inferences_total.labels(
        app_name=app_name,
        hospital_id=hospital_id,
        state=state
    ).inc()


def record_audit_log(action_type: str, user_role: str):
    """Record an audit log entry"""
    audit_logs_written_total.labels(
        action_type=action_type,
        user_role=user_role
    ).inc()


def update_celery_queue_depth(queue_name: str, depth: int):
    """Update Celery queue depth"""
    celery_queue_depth.labels(queue_name=queue_name).set(depth)


def get_metrics_text() -> bytes:
    """Get Prometheus metrics in text format

    Returns:
        Metrics in Prometheus exposition format
    """
    return generate_latest(REGISTRY)


logger.info("Prometheus metrics initialized")
