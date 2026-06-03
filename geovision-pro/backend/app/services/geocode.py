"""Geocoding helpers backed by OpenStreetMap Nominatim (cached, rate-limited)."""
from __future__ import annotations

import asyncio
import time
from typing import Optional

import httpx

from ..config import get_settings
from ..core.cache import geocode_cache

settings = get_settings()
_last_call = 0.0
_lock = asyncio.Lock()


def _headers() -> dict:
    ua = "GeoVisionPro/1.0"
    if settings.nominatim_email:
        ua += f" ({settings.nominatim_email})"
    return {"User-Agent": ua, "Accept": "application/json"}


async def _rate_limited_get(client: httpx.AsyncClient, url: str, params: dict):
    global _last_call
    async with _lock:  # Nominatim asks for <= 1 request/second
        wait = 1.0 - (time.time() - _last_call)
        if wait > 0:
            await asyncio.sleep(wait)
        _last_call = time.time()
    return await client.get(url, params=params, headers=_headers())


async def forward(query: str, limit: int = 3) -> list[dict]:
    """Search a free-text place query -> list of {display, lat, lon, importance}."""
    query = (query or "").strip()
    if not query:
        return []
    cache_key = f"fwd:{limit}:{query.lower()}"
    cached = geocode_cache.get(cache_key)
    if cached is not None:
        return cached
    params = {"format": "jsonv2", "q": query, "limit": limit,
              "accept-language": "de", "addressdetails": 1}
    async with httpx.AsyncClient(timeout=settings.http_timeout) as client:
        try:
            r = await _rate_limited_get(client, f"{settings.nominatim_url}/search", params)
            r.raise_for_status()
            data = r.json()
        except Exception:
            return []
    out = [
        {"display": d.get("display_name", ""), "lat": float(d["lat"]), "lon": float(d["lon"]),
         "importance": float(d.get("importance", 0.0)),
         "country_code": (d.get("address", {}) or {}).get("country_code")}
        for d in data if d.get("lat") and d.get("lon")
    ]
    geocode_cache.set(cache_key, out)
    return out


async def reverse(lat: float, lon: float) -> Optional[dict]:
    """Reverse geocode coordinates -> {display, address}."""
    cache_key = f"rev:{round(lat,5)}:{round(lon,5)}"
    cached = geocode_cache.get(cache_key)
    if cached is not None:
        return cached
    params = {"format": "jsonv2", "lat": lat, "lon": lon, "zoom": 14, "accept-language": "de"}
    async with httpx.AsyncClient(timeout=settings.http_timeout) as client:
        try:
            r = await _rate_limited_get(client, f"{settings.nominatim_url}/reverse", params)
            r.raise_for_status()
            d = r.json()
        except Exception:
            return None
    result = {"display": d.get("display_name", ""), "address": d.get("address", {})}
    geocode_cache.set(cache_key, result)
    return result
