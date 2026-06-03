"""Reference gallery management: grow the app's knowledge with your own photos.

This is the practical, free "train it with more images" path. Upload a geotagged
photo (or give a place/coordinates) and it is embedded and matched against future
uploads. Accuracy for places you cover improves immediately.
"""
from __future__ import annotations

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from ..config import get_settings
from ..services import geocode, reference
from ..services.exif import extract_gps

router = APIRouter(prefix="/reference", tags=["reference"])
settings = get_settings()

_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/heic", "image/heif"}


@router.get("/list")
async def list_reference() -> dict:
    entries = reference.list_entries()
    return {
        "reference_images": len(entries),
        "reference_geolocated": sum(1 for e in entries if e["lat"] is not None),
        "entries": entries[-50:],  # most recent (avoid huge payloads)
    }


@router.post("/reload")
async def reload_reference() -> dict:
    count = reference.reload()
    entries = reference.list_entries()
    return {"reference_images": count,
            "reference_geolocated": sum(1 for e in entries if e["lat"] is not None)}


@router.post("/add")
async def add_reference(
    file: UploadFile = File(...),
    lat: float | None = Form(None),
    lon: float | None = Form(None),
    place: str | None = Form(None),
) -> dict:
    """Add one photo to the gallery. Location is taken from (in order):
    explicit lat/lon → a place name (geocoded) → the photo's own EXIF GPS.
    """
    if file.content_type not in _IMAGE_TYPES:
        raise HTTPException(415, f"Bildformat nicht unterstützt: {file.content_type}")
    data = await file.read()
    if len(data) > settings.upload_max_mb * 1024 * 1024:
        raise HTTPException(413, f"Datei zu groß (> {settings.upload_max_mb} MB).")

    resolved_lat, resolved_lon, how = lat, lon, "Koordinaten"
    if resolved_lat is None or resolved_lon is None:
        if place and place.strip():
            hits = await geocode.forward(place.strip(), limit=1)
            if not hits:
                raise HTTPException(422, f"Ort „{place}“ konnte nicht gefunden werden.")
            resolved_lat, resolved_lon, how = hits[0]["lat"], hits[0]["lon"], f"Ort „{place}“"
        else:
            gps = extract_gps(data)
            if gps.get("lat") is None or gps.get("lon") is None:
                raise HTTPException(
                    422,
                    "Kein Standort angegeben. Gib Koordinaten oder einen Ort an, "
                    "oder lade ein Foto mit GPS-Metadaten hoch.",
                )
            resolved_lat, resolved_lon, how = gps["lat"], gps["lon"], "EXIF-GPS des Fotos"

    if not (-90 <= resolved_lat <= 90 and -180 <= resolved_lon <= 180):
        raise HTTPException(422, "Ungültige Koordinaten.")

    try:
        result = reference.add_image(data, resolved_lat, resolved_lon,
                                     name_hint=file.filename or "")
    except Exception as exc:
        raise HTTPException(500, f"Konnte nicht hinzufügen: {exc}") from exc
    result.update({"lat": resolved_lat, "lon": resolved_lon, "source": how})
    return result
