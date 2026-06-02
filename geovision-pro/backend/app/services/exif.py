"""EXIF / GPS extraction from image bytes — the only exact location source."""
from __future__ import annotations

import io
from typing import Optional

from PIL import Image, ExifTags

# Register HEIC support if pillow-heif is available.
try:  # pragma: no cover - optional dependency
    import pillow_heif

    pillow_heif.register_heif_opener()
    HEIC_SUPPORTED = True
except Exception:  # pragma: no cover
    HEIC_SUPPORTED = False

_GPS_TAG = next((k for k, v in ExifTags.TAGS.items() if v == "GPSInfo"), 34853)
_GPS_KEYS = {v: k for k, v in ExifTags.GPSTAGS.items()}


def _to_degrees(value) -> Optional[float]:
    try:
        d, m, s = value
        return float(d) + float(m) / 60.0 + float(s) / 3600.0
    except Exception:
        return None


def open_image(data: bytes) -> Image.Image:
    """Open arbitrary supported image bytes as RGB."""
    img = Image.open(io.BytesIO(data))
    return img.convert("RGB")


def extract_gps(data: bytes) -> dict:
    """Return a dict with GPS + basic camera metadata. Never raises."""
    out: dict = {"has_gps": False, "lat": None, "lon": None,
                 "altitude": None, "timestamp": None, "camera": None}
    try:
        img = Image.open(io.BytesIO(data))
        exif = img.getexif()
        if not exif:
            return out

        make = exif.get(next((k for k, v in ExifTags.TAGS.items() if v == "Make"), None))
        model = exif.get(next((k for k, v in ExifTags.TAGS.items() if v == "Model"), None))
        if make or model:
            out["camera"] = " ".join(str(x).strip() for x in (make, model) if x)
        dto = exif.get(next((k for k, v in ExifTags.TAGS.items() if v == "DateTimeOriginal"), None))
        if dto:
            out["timestamp"] = str(dto)

        gps = exif.get_ifd(_GPS_TAG) if hasattr(exif, "get_ifd") else None
        if not gps:
            return out

        lat = _to_degrees(gps.get(_GPS_KEYS.get("GPSLatitude")))
        lon = _to_degrees(gps.get(_GPS_KEYS.get("GPSLongitude")))
        lat_ref = gps.get(_GPS_KEYS.get("GPSLatitudeRef"))
        lon_ref = gps.get(_GPS_KEYS.get("GPSLongitudeRef"))
        if lat is not None and lon is not None:
            if lat_ref in ("S", b"S"):
                lat = -lat
            if lon_ref in ("W", b"W"):
                lon = -lon
            out.update(has_gps=True, lat=round(lat, 6), lon=round(lon, 6))

        alt = gps.get(_GPS_KEYS.get("GPSAltitude"))
        if alt is not None:
            try:
                out["altitude"] = round(float(alt), 1)
            except Exception:
                pass
    except Exception:
        return out
    return out
