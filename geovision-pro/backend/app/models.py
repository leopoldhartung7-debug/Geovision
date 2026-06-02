"""ORM models — persisted analyses and their candidates."""
from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Analysis(Base):
    __tablename__ = "analyses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, index=True)
    kind: Mapped[str] = mapped_column(String(16), default="image")  # image | batch | video
    source_name: Mapped[str] = mapped_column(String(255), default="")

    # Best location summary (nullable when not determinable from the image)
    best_label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    best_lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    best_lon: Mapped[float | None] = mapped_column(Float, nullable=True)
    best_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    location_source: Mapped[str] = mapped_column(String(32), default="inference")  # exif | ocr | inference

    # Full structured result (signals, weights, hierarchy, reference matches)
    result: Mapped[dict] = mapped_column(JSON, default=dict)

    candidates: Mapped[list["Candidate"]] = relationship(
        back_populates="analysis", cascade="all, delete-orphan", order_by="Candidate.rank"
    )


class Candidate(Base):
    __tablename__ = "candidates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    analysis_id: Mapped[int] = mapped_column(ForeignKey("analyses.id", ondelete="CASCADE"), index=True)
    rank: Mapped[int] = mapped_column(Integer)
    label: Mapped[str] = mapped_column(String(255))
    confidence: Mapped[float] = mapped_column(Float)
    lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    lon: Mapped[float | None] = mapped_column(Float, nullable=True)
    reasoning: Mapped[str] = mapped_column(Text, default="")

    analysis: Mapped[Analysis] = relationship(back_populates="candidates")
