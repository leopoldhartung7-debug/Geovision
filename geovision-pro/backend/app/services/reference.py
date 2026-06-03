"""Reference image gallery — real image-retrieval geolocation.

HONEST DESIGN: there is no bundled "global image database" (that would be a fake).
Instead, point GEOVISION_REFERENCE_DIR at a folder of YOUR OWN geotagged images.
We embed them once (cached to disk so restarts and additions are cheap) and match
new photos against them with cosine similarity. This is exactly how commercial
tools pinpoint a place: retrieval against known, located images.

"Training with more images" lives here: the more geotagged photos you drop into
the folder, the more places the app can recognise — no GPU, no retraining.

Each reference image gets coordinates from, in order:
  1. its EXIF GPS, or
  2. a "lat,lon" pattern in its filename, e.g.  cafe_48.8584_2.2945.jpg
Images without coordinates are still indexed (they show as look-alikes) but do
not contribute to the location estimate.
"""
from __future__ import annotations

import logging
import os
import re
import threading

import numpy as np

from ..config import get_settings
from .exif import extract_gps, open_image
from .vision import get_engine

logger = logging.getLogger(__name__)
settings = get_settings()

_IMG_EXT = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
_CACHE_NAME = ".geovision_ref_index.npz"
_COORD_RE = re.compile(r"(-?\d{1,2}\.\d{3,})[,_ ]+(-?\d{1,3}\.\d{3,})")

_index: list[dict] | None = None
_lock = threading.Lock()


def coords_from_name(name: str) -> tuple[float, float] | tuple[None, None]:
    """Parse a 'lat,lon' (or 'lat_lon') pattern from a filename. (None, None) if absent."""
    m = _COORD_RE.search(os.path.splitext(os.path.basename(name))[0])
    if not m:
        return None, None
    lat, lon = float(m.group(1)), float(m.group(2))
    if -90 <= lat <= 90 and -180 <= lon <= 180:
        return lat, lon
    return None, None


def _scan(root: str) -> list[tuple[str, float]]:
    """Recursively list (relative_path, mtime) for supported images under root."""
    found: list[tuple[str, float]] = []
    for dirpath, _dirs, files in os.walk(root):
        for fname in files:
            if os.path.splitext(fname)[1].lower() not in _IMG_EXT:
                continue
            full = os.path.join(dirpath, fname)
            rel = os.path.relpath(full, root)
            try:
                found.append((rel, os.path.getmtime(full)))
            except OSError:
                continue
    return sorted(found)


def _load_cache(root: str) -> dict[str, dict]:
    """Load the on-disk embedding cache keyed by relative path -> {vec, lat, lon, mtime}."""
    path = os.path.join(root, _CACHE_NAME)
    if not os.path.isfile(path):
        return {}
    try:
        npz = np.load(path, allow_pickle=True)
        names = npz["names"]
        vecs = npz["vecs"]
        lats = npz["lats"]
        lons = npz["lons"]
        mtimes = npz["mtimes"]
    except Exception as exc:
        logger.warning("Reference cache unreadable (%s) — rebuilding.", exc)
        return {}
    out: dict[str, dict] = {}
    for i, name in enumerate(names):
        lat = float(lats[i]); lon = float(lons[i])
        out[str(name)] = {
            "vec": vecs[i].astype("float32"),
            "lat": None if np.isnan(lat) else lat,
            "lon": None if np.isnan(lon) else lon,
            "mtime": float(mtimes[i]),
        }
    return out


def _save_cache(root: str, entries: list[dict]) -> None:
    path = os.path.join(root, _CACHE_NAME)
    try:
        np.savez(
            path,
            names=np.array([e["name"] for e in entries], dtype=object),
            vecs=np.array([e["vec"] for e in entries], dtype="float32"),
            lats=np.array([np.nan if e["lat"] is None else e["lat"] for e in entries], dtype="float64"),
            lons=np.array([np.nan if e["lon"] is None else e["lon"] for e in entries], dtype="float64"),
            mtimes=np.array([e["mtime"] for e in entries], dtype="float64"),
        )
    except Exception as exc:
        logger.warning("Could not write reference cache: %s", exc)


def _build_index() -> list[dict]:
    root = settings.reference_dir
    if not root or not os.path.isdir(root):
        return []
    scanned = _scan(root)
    if not scanned:
        return []
    cache = _load_cache(root)
    engine = get_engine()
    entries: list[dict] = []
    embedded = reused = 0
    for rel, mtime in scanned:
        cached = cache.get(rel)
        if cached is not None and abs(cached["mtime"] - mtime) < 1e-6:
            entries.append({"name": rel, "vec": cached["vec"],
                            "lat": cached["lat"], "lon": cached["lon"], "mtime": mtime})
            reused += 1
            continue
        full = os.path.join(root, rel)
        try:
            with open(full, "rb") as fh:
                data = fh.read()
            vec = engine.embed_image(open_image(data))
            gps = extract_gps(data)
            lat, lon = gps.get("lat"), gps.get("lon")
            if lat is None or lon is None:
                lat, lon = coords_from_name(rel)
            entries.append({"name": rel, "vec": vec, "lat": lat, "lon": lon, "mtime": mtime})
            embedded += 1
        except Exception as exc:
            logger.warning("Reference image %s skipped: %s", rel, exc)
    if embedded:
        _save_cache(root, entries)
    located = sum(1 for e in entries if e["lat"] is not None)
    logger.info("Reference index: %d images (%d new, %d cached, %d geolocated).",
                len(entries), embedded, reused, located)
    return entries


def get_index() -> list[dict]:
    global _index
    if _index is None:
        with _lock:
            if _index is None:
                _index = _build_index()
    return _index


def reload() -> int:
    """Force a rebuild (e.g. after adding images). Returns the image count."""
    global _index
    with _lock:
        _index = _build_index()
    return len(_index)


def match(image_vec: "np.ndarray", top_k: int = 5) -> list[dict]:
    """Top-k look-alikes by cosine similarity (for display)."""
    idx = get_index()
    if not idx:
        return []
    sims = [
        {"name": e["name"], "similarity": round(float(np.dot(image_vec, e["vec"])), 4),
         "lat": e["lat"], "lon": e["lon"]}
        for e in idx
    ]
    sims.sort(key=lambda x: x["similarity"], reverse=True)
    return sims[:top_k]


def geolocate(image_vec: "np.ndarray") -> dict | None:
    """Retrieval-based location estimate from the geotagged references.

    Fuses the nearest geotagged neighbours (cosine >= threshold) into a
    similarity-weighted centroid. Returns None if nothing clears the bar, so the
    pipeline cleanly falls through to the next source.
    """
    idx = get_index()
    if not idx:
        return None
    located = [e for e in idx if e["lat"] is not None and e["lon"] is not None]
    if not located:
        return None
    scored = sorted(
        ((float(np.dot(image_vec, e["vec"])), e) for e in located),
        key=lambda x: x[0], reverse=True,
    )
    top = [(s, e) for s, e in scored[: settings.reference_use_top_k]
           if s >= settings.reference_min_similarity]
    if not top:
        return None
    wsum = sum(s for s, _ in top) or 1.0
    lat = sum(s * e["lat"] for s, e in top) / wsum
    lon = sum(s * e["lon"] for s, e in top) / wsum
    matches = [{"name": e["name"], "similarity": round(s, 4),
                "lat": e["lat"], "lon": e["lon"]} for s, e in top]
    return {
        "lat": lat, "lon": lon,
        "similarity": top[0][0],            # best single match (confidence proxy)
        "n": len(top),
        "matches": matches,
    }
