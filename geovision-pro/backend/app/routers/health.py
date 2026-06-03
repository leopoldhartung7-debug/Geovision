"""Health & model status endpoints."""
from fastapi import APIRouter

from ..config import get_settings
from ..services import ocr, picarta, reference
from ..services.geoengine import get_geo_engine
from ..services.vision import get_engine

router = APIRouter(tags=["system"])
settings = get_settings()


@router.get("/health")
async def health() -> dict:
    return {"status": "ok", "app": settings.app_name}


@router.get("/status")
async def status() -> dict:
    engine = get_engine()
    idx = reference.get_index()
    geolocated = sum(1 for e in idx if e.get("lat") is not None)
    return {
        "model_configured": settings.vision_model,
        "model_loaded": engine.loaded,
        "model_in_use": engine.model_name or None,
        "ocr_available": ocr.available(),
        "picarta_enabled": picarta.available(),
        "geoclip_enabled": get_geo_engine().available,
        "reference_images": len(idx),
        "reference_geolocated": geolocated,
        "reference_dir": reference.active_dir() or None,
        "device": settings.device,
    }
