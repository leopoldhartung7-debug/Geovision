"""A tiny thread-safe in-memory LRU+TTL cache for geocoding and embeddings.

Deliberately dependency-free. For multi-process deployments swap this for Redis;
the call sites only use get()/set().
"""
import threading
import time
from collections import OrderedDict
from typing import Any, Optional


class TTLCache:
    def __init__(self, maxsize: int = 1024, ttl: float = 3600.0) -> None:
        self._data: "OrderedDict[str, tuple[float, Any]]" = OrderedDict()
        self._maxsize = maxsize
        self._ttl = ttl
        self._lock = threading.Lock()

    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            item = self._data.get(key)
            if item is None:
                return None
            ts, value = item
            if time.time() - ts > self._ttl:
                self._data.pop(key, None)
                return None
            self._data.move_to_end(key)
            return value

    def set(self, key: str, value: Any) -> None:
        with self._lock:
            self._data[key] = (time.time(), value)
            self._data.move_to_end(key)
            while len(self._data) > self._maxsize:
                self._data.popitem(last=False)


geocode_cache = TTLCache(maxsize=2048, ttl=24 * 3600)
