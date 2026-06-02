"""Health & model status endpoints."""
from fastapi import APIRouter

from ..config import get_settings
from ..services import ocr
from ..services.reference import get_index
from ..services.vision import get_engine

router = APIRouter(tags=["system"])
settings = get_settings()


@router.get("/health")
async def health() -> dict:
    return {"status": "ok", "app": settings.app_name}


@router.get("/status")
async def status() -> dict:
    engine = get_engine()
    return {
        "model_configured": settings.vision_model,
        "model_loaded": engine.loaded,
        "model_in_use": engine.model_name or None,
        "ocr_available": ocr.available(),
        "reference_images": len(get_index()),
        "device": settings.device,
    }
