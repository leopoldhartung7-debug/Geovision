"""Pydantic response/request schemas."""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class GpsInfo(BaseModel):
    has_gps: bool = False
    lat: Optional[float] = None
    lon: Optional[float] = None
    altitude: Optional[float] = None
    timestamp: Optional[str] = None
    camera: Optional[str] = None
    address: Optional[str] = None


class SignalScore(BaseModel):
    label: str
    score: float


class SignalGroup(BaseModel):
    """One visual-analysis category with its top zero-shot matches."""
    name: str                 # e.g. "Landschaft", "Architektur"
    top: list[SignalScore]
    weight: float             # normalized contribution 0..1


class LocationCandidate(BaseModel):
    rank: int
    label: str
    confidence: float
    lat: Optional[float] = None
    lon: Optional[float] = None
    reasoning: str = ""


class Hierarchy(BaseModel):
    continent: Optional[str] = None
    country: Optional[str] = None
    region: Optional[str] = None
    city: Optional[str] = None
    district: Optional[str] = None
    # Honest note about which levels could not be derived
    note: str = ""


class ReferenceMatch(BaseModel):
    name: str
    similarity: float
    lat: Optional[float] = None
    lon: Optional[float] = None


class AnalysisResult(BaseModel):
    id: Optional[int] = None
    created_at: Optional[datetime] = None
    kind: str = "image"
    source_name: str = ""

    gps: GpsInfo = GpsInfo()
    location_source: str = "inference"   # exif | ocr | inference
    hierarchy: Hierarchy = Hierarchy()
    candidates: list[LocationCandidate] = []
    signals: list[SignalGroup] = []
    ocr_text: str = ""
    reference_matches: list[ReferenceMatch] = []
    uncertainty: str = ""
    model_used: str = ""


class AnalysisListItem(BaseModel):
    id: int
    created_at: datetime
    kind: str
    source_name: str
    best_label: Optional[str]
    best_confidence: Optional[float]
    location_source: str

    class Config:
        from_attributes = True
