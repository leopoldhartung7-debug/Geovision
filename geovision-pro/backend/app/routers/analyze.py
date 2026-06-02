"""Analysis endpoints: single image, batch, and video."""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings
from ..database import get_session
from ..models import Analysis, Candidate
from ..schemas import AnalysisResult
from ..services import fusion

router = APIRouter(prefix="/analyze", tags=["analyze"])
settings = get_settings()

_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/heic", "image/heif"}
_VIDEO_TYPES = {"video/mp4", "video/quicktime", "video/x-msvideo"}


async def _read_limited(file: UploadFile) -> bytes:
    data = await file.read()
    if len(data) > settings.upload_max_mb * 1024 * 1024:
        raise HTTPException(413, f"Datei zu groß (> {settings.upload_max_mb} MB).")
    return data


async def _persist(session: AsyncSession, result: AnalysisResult) -> AnalysisResult:
    best = result.candidates[0] if result.candidates else None
    row = Analysis(
        kind=result.kind, source_name=result.source_name,
        best_label=best.label if best else None,
        best_lat=best.lat if best else None,
        best_lon=best.lon if best else None,
        best_confidence=best.confidence if best else None,
        location_source=result.location_source,
        result=result.model_dump(mode="json"),
    )
    for c in result.candidates:
        row.candidates.append(Candidate(
            rank=c.rank, label=str(c.label), confidence=c.confidence,
            lat=c.lat, lon=c.lon, reasoning=c.reasoning))
    session.add(row)
    await session.commit()
    await session.refresh(row)
    result.id = row.id
    result.created_at = row.created_at
    return result


@router.post("/image", response_model=AnalysisResult)
async def analyze_image(file: UploadFile = File(...), session: AsyncSession = Depends(get_session)):
    if file.content_type not in _IMAGE_TYPES:
        raise HTTPException(415, f"Bildformat nicht unterstützt: {file.content_type}")
    data = await _read_limited(file)
    try:
        result = await fusion.analyze_image(data, source_name=file.filename or "")
    except Exception as exc:
        raise HTTPException(500, f"Analyse fehlgeschlagen: {exc}") from exc
    return await _persist(session, result)


@router.post("/batch", response_model=list[AnalysisResult])
async def analyze_batch(files: list[UploadFile] = File(...),
                        session: AsyncSession = Depends(get_session)):
    if not files:
        raise HTTPException(400, "Keine Dateien.")
    results: list[AnalysisResult] = []
    for file in files:
        if file.content_type not in _IMAGE_TYPES:
            continue
        data = await _read_limited(file)
        try:
            res = await fusion.analyze_image(data, source_name=file.filename or "")
            results.append(await _persist(session, res))
        except Exception as exc:  # keep batch going
            results.append(AnalysisResult(source_name=file.filename or "",
                                          uncertainty=f"Fehler: {exc}"))
    return results


@router.post("/video", response_model=AnalysisResult)
async def analyze_video(file: UploadFile = File(...), session: AsyncSession = Depends(get_session)):
    if file.content_type not in _VIDEO_TYPES:
        raise HTTPException(415, f"Videoformat nicht unterstützt: {file.content_type}")
    data = await _read_limited(file)
    try:
        result = await fusion.analyze_video(data, source_name=file.filename or "")
    except Exception as exc:
        raise HTTPException(500, f"Videoanalyse fehlgeschlagen: {exc}") from exc
    return await _persist(session, result)
