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
from uuid import uuid4

import numpy as np

from ..config import get_settings
from .exif import extract_gps, open_image
from .vision import get_engine

logger = logging.getLogger(__name__)
settings = get_settings()

_IMG_EXT = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
_CACHE_NAME = ".geovision_ref_index.npz"
_COORD_RE = re.compile(r"(-?\d{1,2}\.\d{3,})[,_ ]+(-?\d{1,3}\.\d{3,})")
_FALLBACK_DIR = "/tmp/geovision_reference"

_index: list[dict] | None = None
_dir_override: str | None = None
_lock = threading.Lock()


def active_dir() -> str:
    """The reference folder currently in use (may be a writable fallback)."""
    return _dir_override or settings.reference_dir


def ensure_writable_dir() -> str:
    """Return a writable reference folder, creating it; fall back to /tmp if the
    configured dir (e.g. /data without persistent storage) is not writable."""
    global _dir_override
    target = active_dir()
    for candidate in (target, _FALLBACK_DIR):
        if not candidate:
            continue
        try:
            os.makedirs(candidate, exist_ok=True)
            probe = os.path.join(candidate, ".write_test")
            with open(probe, "w") as fh:
                fh.write("ok")
            os.remove(probe)
            if candidate != target:
                _dir_override = candidate
                logger.warning("Reference dir %s not writable — using %s instead.", target, candidate)
            return candidate
        except OSError:
            continue
    raise RuntimeError("No writable reference directory available.")


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
    root = active_dir()
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


def list_entries() -> list[dict]:
    """Current gallery contents (for the UI): name + coordinates, newest last."""
    return [{"name": e["name"], "lat": e["lat"], "lon": e["lon"]} for e in get_index()]


def add_image(data: bytes, lat: float, lon: float, name_hint: str = "") -> dict:
    """Add one geotagged photo to the gallery: embed it, persist it (with the
    coordinates encoded in the filename so it survives a rebuild that re-scans
    the folder), and append it to the live in-memory index — effective at once.
    """
    root = ensure_writable_dir()
    engine = get_engine()
    image = open_image(data)
    vec = engine.embed_image(image)
    # letters-only stem keeps the coordinate parser unambiguous
    safe = re.sub(r"[^A-Za-z]+", "", name_hint)[:30] or "ref"
    fname = f"{safe}-{uuid4().hex[:6]}_{float(lat):.5f}_{float(lon):.5f}.jpg"
    path = os.path.join(root, fname)
    image.convert("RGB").save(path, "JPEG", quality=92)

    idx = get_index()  # build (without the new file) before appending
    idx.append({"name": fname, "vec": vec,
                "lat": float(lat), "lon": float(lon),
                "mtime": os.path.getmtime(path)})
    _save_cache(root, idx)
    return {
        "name": fname,
        "reference_images": len(idx),
        "reference_geolocated": sum(1 for e in idx if e["lat"] is not None),
    }


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
