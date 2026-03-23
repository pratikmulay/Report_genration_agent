"""
Redis cache for report metadata.
Falls back gracefully if Redis is unavailable.
"""

import json
import logging
from typing import Optional

from app.config import settings
from app.models import ReportMetadata

logger = logging.getLogger(__name__)

_redis_client = None


def _get_redis():
    """Lazy-initialize Redis connection."""
    global _redis_client
    if _redis_client is None:
        try:
            import redis

            _redis_client = redis.from_url(
                settings.REDIS_URL,
                decode_responses=True,
                socket_connect_timeout=3,
            )
            _redis_client.ping()
            logger.info("Redis connection established")
        except Exception as e:
            logger.warning(f"Redis unavailable, caching disabled: {e}")
            _redis_client = None
    return _redis_client


async def store_report_metadata(
    report_id: str,
    metadata: ReportMetadata,
    ttl: Optional[int] = None,
) -> bool:
    """Store report metadata in Redis with TTL. Returns True on success."""
    r = _get_redis()
    if r is None:
        return False

    try:
        key = f"report:{report_id}"
        data = metadata.model_dump_json()
        r.setex(key, ttl or settings.REPORT_CACHE_TTL, data)
        logger.info(f"Cached report metadata: {key}")
        return True
    except Exception as e:
        logger.warning(f"Failed to cache report metadata: {e}")
        return False


async def get_report_metadata(report_id: str) -> Optional[ReportMetadata]:
    """Retrieve report metadata from Redis. Returns None on miss or error."""
    r = _get_redis()
    if r is None:
        return None

    try:
        key = f"report:{report_id}"
        data = r.get(key)
        if data is None:
            return None
        return ReportMetadata.model_validate_json(data)
    except Exception as e:
        logger.warning(f"Failed to retrieve report metadata: {e}")
        return None


async def health_check() -> bool:
    """Check if Redis is reachable."""
    r = _get_redis()
    if r is None:
        return False
    try:
        return r.ping()
    except Exception:
        return False
