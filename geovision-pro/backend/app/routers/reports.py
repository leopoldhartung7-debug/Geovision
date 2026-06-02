"""Report export endpoints (PDF / CSV / JSON) for a stored analysis."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_session
from ..models import Analysis
from ..schemas import AnalysisResult
from ..services import report

router = APIRouter(prefix="/report", tags=["report"])


async def _load(job_id: int, session: AsyncSession) -> AnalysisResult:
    row = await session.get(Analysis, job_id)
    if not row:
        raise HTTPException(404, "Analyse nicht gefunden.")
    data = dict(row.result)
    data["id"] = row.id
    data["created_at"] = row.created_at
    return AnalysisResult.model_validate(data)


@router.get("/{job_id}.json")
async def report_json(job_id: int, session: AsyncSession = Depends(get_session)):
    result = await _load(job_id, session)
    return Response(report.to_json_bytes(result), media_type="application/json",
                    headers={"Content-Disposition": f'attachment; filename="geovision_{job_id}.json"'})


@router.get("/{job_id}.csv")
async def report_csv(job_id: int, session: AsyncSession = Depends(get_session)):
    result = await _load(job_id, session)
    return Response(report.to_csv_bytes(result), media_type="text/csv",
                    headers={"Content-Disposition": f'attachment; filename="geovision_{job_id}.csv"'})


@router.get("/{job_id}.pdf")
async def report_pdf(job_id: int, session: AsyncSession = Depends(get_session)):
    result = await _load(job_id, session)
    try:
        pdf = report.to_pdf_bytes(result)
    except Exception as exc:
        raise HTTPException(500, f"PDF-Erzeugung fehlgeschlagen: {exc}") from exc
    return Response(pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="geovision_{job_id}.pdf"'})
