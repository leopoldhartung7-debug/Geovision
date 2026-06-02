"""Reference image similarity.

HONEST DESIGN: there is no bundled "global image database" (that would be a fake).
Instead, if you point GEOVISION_REFERENCE_DIR at a folder of your own geotagged
images, we embed them once and return real cosine-similarity matches. If the folder
is empty/unset, this returns [] and the UI falls back to a Google-Lens hand-off.
"""
from __future__ import annotations

import logging
import os
import threading

import numpy as np

from ..config import get_settings
from .exif import extract_gps, open_image
from .vision import get_engine

logger = logging.getLogger(__name__)
settings = get_settings()

_IMG_EXT = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
_index: list[dict] | None = None
_lock = threading.Lock()


def _build_index() -> list[dict]:
    entries: list[dict] = []
    root = settings.reference_dir
    if not root or not os.path.isdir(root):
        return entries
    engine = get_engine()
    for fname in sorted(os.listdir(root)):
        ext = os.path.splitext(fname)[1].lower()
        if ext not in _IMG_EXT:
            continue
        path = os.path.join(root, fname)
        try:
            with open(path, "rb") as fh:
                data = fh.read()
            vec = engine.embed_image(open_image(data))
            gps = extract_gps(data)
            entries.append({"name": fname, "vec": vec,
                            "lat": gps.get("lat"), "lon": gps.get("lon")})
        except Exception as exc:
            logger.warning("Reference image %s skipped: %s", fname, exc)
    logger.info("Reference index built: %d images", len(entries))
    return entries


def get_index() -> list[dict]:
    global _index
    if _index is None:
        with _lock:
            if _index is None:
                _index = _build_index()
    return _index


def match(image_vec: "np.ndarray", top_k: int = 5) -> list[dict]:
    idx = get_index()
    if not idx:
        return []
    sims = []
    for e in idx:
        sim = float(np.dot(image_vec, e["vec"]))  # both L2-normalized -> cosine
        sims.append({"name": e["name"], "similarity": round(sim, 4),
                     "lat": e["lat"], "lon": e["lon"]})
    sims.sort(key=lambda x: x["similarity"], reverse=True)
    return sims[:top_k]
