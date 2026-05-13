"""Simple in-memory TTL cache for recommendation results."""
import time
import threading

_cache: dict = {}
_lock = threading.Lock()


def get(key: str):
    with _lock:
        entry = _cache.get(key)
        if entry and time.time() < entry["expires"]:
            return entry["value"]
        if entry:
            del _cache[key]
        return None


def set(key: str, value, ttl: int = 900):
    with _lock:
        _cache[key] = {"value": value, "expires": time.time() + ttl}


def invalidate(key: str):
    with _lock:
        _cache.pop(key, None)


def clear_all():
    with _lock:
        _cache.clear()
