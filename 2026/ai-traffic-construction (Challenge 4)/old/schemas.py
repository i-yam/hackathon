from __future__ import annotations
from pydantic import BaseModel
from typing import List, Optional


class RecommendationRequest(BaseModel):
    section: int
    total_hours: int
    filter: str = "traffic"
    top_n: int = 3


class WindowResult(BaseModel):
    rank: int
    period: str
    dates: str
    score: int          # 0–100, higher = better (less disruptive)
    week_start: int     # 0-indexed week offset from HORIZON_START
    week_span: int
    mean_kfz_per_hour: int
    lkw_share_pct: float
    congestion_pct: float


class KpiResult(BaseModel):
    mean_kfz_per_hour: int
    lkw_share_pct: float
    congestion_pct: float
    risk: str           # 'niedrig' | 'mittel' | 'hoch'


class RecommendationResponse(BaseModel):
    windows: List[WindowResult]
    kpi: Optional[KpiResult] = None


class HeatWeek(BaseModel):
    week_index: int
    score: int          # 0–100, higher = better
    month_label: str    # non-empty only on first week of a new month


class HeatmapResponse(BaseModel):
    weeks: List[HeatWeek]


class SectionInfo(BaseModel):
    id: int
    name: str
    km: str


class SectionsResponse(BaseModel):
    sections: List[SectionInfo]
    horizon_start: str  # ISO date string, e.g. "2026-06-22"
