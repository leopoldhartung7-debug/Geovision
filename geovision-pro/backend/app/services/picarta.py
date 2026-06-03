"""Picarta predictor — the commercial, GeoSpy-class location API.

Picarta (https://picarta.ai) is the closest publicly-available service to
GeoSpy in accuracy: it routinely returns city- and street-level guesses, not
just a country. It is OPTIONAL and OFF unless a token is configured:

  * Set GEOVISION_PICARTA_API_TOKEN to your (free-tier) token to enable it.
  * Without a token, ``available`` is False and the pipeline transparently
    falls back to the open models (reference retrieval / GeoCLIP / StreetCLIP).

Honesty note: this sends the image to an external service. We only call it when
a token is explicitly set, and we say so in the result's source label.
"""
from __future__ import annotations

import base64
import logging
from typing import Optional

import httpx

from ..config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


def available() -> bool:
    return bool(settings.enable_picarta and settings.picarta_api_token.strip())


def _coerce_float(value) -> Optional[float]:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _gps_from_entry(entry: dict) -> tuple[Optional[float], Optional[float]]:
    """Pull (lat, lon) out of one prediction entry across Picarta's field shapes."""
    gps = entry.get("gps")
    if isinstance(gps, (list, tuple)) and len(gps) >= 2:
        return _coerce_float(gps[0]), _coerce_float(gps[1])
    lat = entry.get("ai_lat", entry.get("lat", entry.get("latitude")))
    lon = entry.get("ai_lon", entry.get("lon", entry.get("longitude")))
    return _coerce_float(lat), _coerce_float(lon)


def parse_response(data: dict) -> list[dict]:
    """Normalise a Picarta response into [{lat, lon, confidence, country, city,
    province}, ...] best-first. Pure function (no I/O) so it is unit-testable.
    """
    if not isinstance(data, dict):
        return []
    out: list[dict] = []

    topk = data.get("topk_predictions_dict")
    if isinstance(topk, dict):
        # keys are usually "1", "2", ... -> sort numerically when possible
        def _key(k):
            try:
                return int(k)
            except (TypeError, ValueError):
                return 1_000_000
        for k in sorted(topk.keys(), key=_key):
            entry = topk[k] or {}
            addr = entry.get("address") if isinstance(entry.get("address"), dict) else entry
            lat, lon = _gps_from_entry(entry)
            if lat is None or lon is None:
                continue
            out.append({
                "lat": lat, "lon": lon,
                "confidence": _coerce_float(entry.get("confidence")) or 0.0,
                "country": addr.get("country"),
                "city": addr.get("city") or addr.get("town"),
                "province": addr.get("province") or addr.get("state"),
            })

    if not out:
        # fall back to the single top-level prediction
        lat = _coerce_float(data.get("ai_lat"))
        lon = _coerce_float(data.get("ai_lon"))
        if lat is not None and lon is not None:
            out.append({
                "lat": lat, "lon": lon,
                "confidence": _coerce_float(data.get("ai_confidence")) or 0.0,
                "country": data.get("ai_country"),
                "city": data.get("ai_city"),
                "province": data.get("ai_province"),
            })
    return out


async def predict(image_bytes: bytes) -> list[dict]:
    """Call Picarta and return normalised predictions. [] on any failure."""
    if not available():
        return []
    payload = {
        "TOKEN": settings.picarta_api_token.strip(),
        "IMAGE": base64.b64encode(image_bytes).decode("ascii"),
        "TOP_K": settings.picarta_top_k,
    }
    try:
        async with httpx.AsyncClient(timeout=settings.http_timeout) as client:
            r = await client.post(settings.picarta_url, json=payload,
                                  headers={"Content-Type": "application/json"})
            r.raise_for_status()
            data = r.json()
    except Exception as exc:
        logger.warning("Picarta request failed (%s) — falling back to open models.", exc)
        return []
    preds = parse_response(data)
    if not preds:
        logger.info("Picarta returned no usable prediction; falling back.")
    return preds
