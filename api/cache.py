import os
import redis
from functools import lru_cache

_redis_client = None

def get_cache():
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.Redis(
            host=os.getenv('REDIS_HOST', 'localhost'),
            port=int(os.getenv('REDIS_PORT', 6379)),
            password=os.getenv('REDIS_PASSWORD', 'diplom123'),
            decode_responses=True
        )
    return _redis_client

def cache_get(key: str):
    try:
        return get_cache().get(key)
    except Exception:
        return None

def cache_set(key: str, value: str, ttl: int = 60):
    try:
        get_cache().setex(key, ttl, value)
    except Exception:
        pass
