"""Optional OCR via Tesseract (host binary). Reads signs/place names from images.

Per project boundary: this is general signage/text reading. It is NOT used for
license-plate numbers or person identification.
"""
from __future__ import annotations

import logging
import re

from PIL import Image, ImageOps

from ..config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

try:  # pragma: no cover - optional dependency
    import pytesseract

    _TESS = True
except Exception:  # pragma: no cover
    _TESS = False


def available() -> bool:
    if not (settings.enable_ocr and _TESS):
        return False
    try:
        pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False


def _preprocess(image: Image.Image) -> Image.Image:
    gray = ImageOps.grayscale(image)
    gray = ImageOps.autocontrast(gray, cutoff=2)
    w, h = gray.size
    longest = max(w, h)
    if longest < 1600:
        scale = min(2.5, 1600 / longest)
        gray = gray.resize((int(w * scale), int(h * scale)))
    return gray


def read_text(image: Image.Image, lang: str = "deu+eng") -> str:
    if not available():
        return ""
    try:
        txt = pytesseract.image_to_string(_preprocess(image), lang=lang)
    except Exception as exc:  # missing language pack etc.
        logger.warning("OCR failed: %s", exc)
        return ""
    return txt.strip()


def candidate_queries(text: str, max_queries: int = 4) -> list[str]:
    """Turn OCR text into geocodable place-name candidates."""
    lines = []
    for raw in text.splitlines():
        cleaned = re.sub(r"[^\w\s\-.,&äöüÄÖÜß]", " ", raw, flags=re.UNICODE)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        if len(cleaned) >= 3 and re.search(r"[A-Za-zÄÖÜäöü]{3,}", cleaned):
            lines.append(cleaned)
    queries: list[str] = []
    if lines:
        queries.append(", ".join(lines[:4]))
    queries.extend(l for l in lines[:5] if len(l) >= 4)
    # de-duplicate preserving order
    seen, out = set(), []
    for q in queries:
        if q.lower() not in seen:
            seen.add(q.lower())
            out.append(q)
    return out[:max_queries]
