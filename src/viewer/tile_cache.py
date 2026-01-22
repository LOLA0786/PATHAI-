"""Tile Cache - Redis LRU for fast loads

Why: Reduce S3 reads, <3s tile time.
How: Cache PNG bytes 24h.
"""
import redis
import structlog

logger = structlog.get_logger()
r = redis.Redis(host='localhost', port=6379, db=0)  # Prod: ElastiCache

def get_cached_tile(key: str) -> bytes | None:
    return r.get(key)

def cache_tile(key: str, tile_bytes: bytes):
    r.setex(key, 86400, tile_bytes)  # 24h
    logger.info("Tile cached", key=key)

# LRU: Redis handles with MAXMEMORY policy allkeys-lru
