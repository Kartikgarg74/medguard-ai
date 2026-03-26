"""In-memory TTL cache to avoid excessive API/scraping calls."""

import logging
import time
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    value: Any
    expires_at: float


class TTLCache:
    """Simple in-memory cache with TTL expiration."""

    def __init__(self):
        self._store: dict[str, CacheEntry] = {}
        self._hits = 0
        self._misses = 0

    def get(self, key: str) -> Any | None:
        entry = self._store.get(key)
        if entry is None:
            self._misses += 1
            return None
        if time.time() > entry.expires_at:
            del self._store[key]
            self._misses += 1
            return None
        self._hits += 1
        return entry.value

    def set(self, key: str, value: Any, ttl_seconds: int = 60) -> None:
        self._store[key] = CacheEntry(value=value, expires_at=time.time() + ttl_seconds)

    def delete(self, key: str) -> None:
        self._store.pop(key, None)

    def clear(self) -> None:
        self._store.clear()

    def cleanup(self) -> int:
        now = time.time()
        expired = [k for k, v in self._store.items() if now > v.expires_at]
        for k in expired:
            del self._store[k]
        return len(expired)

    @property
    def stats(self) -> dict:
        total = self._hits + self._misses
        return {
            "size": len(self._store),
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": f"{(self._hits / total * 100):.1f}%" if total > 0 else "N/A",
        }


# Global cache instance
_cache = TTLCache()

# TTL presets for MedGuard (seconds)
NPPA_CEILING_TTL = 86400  # Ceiling prices: 24 hours (rarely change)
PHARMACY_PRICE_TTL = 3600  # Pharmacy prices: 1 hour
COMPLIANCE_RESULT_TTL = 1800  # Compliance checks: 30 minutes
MEDICINE_INFO_TTL = 43200  # Medicine catalog: 12 hours


def get_cache() -> TTLCache:
    return _cache


def cached_ceiling_price(medicine_id: str) -> Any | None:
    return _cache.get(f"ceiling:{medicine_id}")


def set_cached_ceiling_price(medicine_id: str, data: dict) -> None:
    _cache.set(f"ceiling:{medicine_id}", data, NPPA_CEILING_TTL)


def cached_pharmacy_price(medicine_id: str, platform: str) -> Any | None:
    return _cache.get(f"pharmacy:{platform}:{medicine_id}")


def set_cached_pharmacy_price(medicine_id: str, platform: str, data: dict) -> None:
    _cache.set(f"pharmacy:{platform}:{medicine_id}", data, PHARMACY_PRICE_TTL)
