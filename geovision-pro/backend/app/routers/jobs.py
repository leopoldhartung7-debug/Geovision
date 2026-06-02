"""History / stored analyses."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_session
from ..models import Analysis
from ..schemas import AnalysisListItem, AnalysisResult

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("", response_model=list[AnalysisListItem])
async def list_jobs(limit: int = 50, session: AsyncSession = Depends(get_session)):
    rows = (await session.execute(
        select(Analysis).order_by(desc(Analysis.created_at)).limit(min(limit, 200))
    )).scalars().all()
    return rows


@router.get("/{job_id}", response_model=AnalysisResult)
async def get_job(job_id: int, session: AsyncSession = Depends(get_session)):
    row = await session.get(Analysis, job_id)
    if not row:
        raise HTTPException(404, "Analyse nicht gefunden.")
    data = dict(row.result)
    data["id"] = row.id
    data["created_at"] = row.created_at
    return AnalysisResult.model_validate(data)


@router.delete("/{job_id}")
async def delete_job(job_id: int, session: AsyncSession = Depends(get_session)):
    row = await session.get(Analysis, job_id)
    if not row:
        raise HTTPException(404, "Analyse nicht gefunden.")
    await session.delete(row)
    await session.commit()
    return {"deleted": job_id}
