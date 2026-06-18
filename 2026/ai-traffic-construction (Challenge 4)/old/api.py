"""
A3 Bau-Fenster API
==================
FastAPI old for the construction-window planner frontend.

Endpoints
---------
GET  /sections           — static list of the 5 A3 route sections
POST /recommendations    — ranked top-N windows for a section/duration/filter
GET  /heatmap-data       — 52-week suitability scores for the year heatmap

Start with:
    uvicorn old.api:app --reload
or from the old/ directory:
    uvicorn api:app --reload
"""
from __future__ import annotations

import os
import sys
from datetime import date, timedelta

import pandas as pd
from datetime import datetime as _dt_parse
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

# Add old/ (for schemas.py) and project root (for recommend_windows.py) to sys.path
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.dirname(_HERE))

from recommend_windows import (
    CapacityConfig,
    ContinuousDuration,
    ScoringWeights,
    compute_burden,
    get_recommendations,
    load_assets,
)
from schemas import (
    HeatmapResponse,
    HeatWeek,
    KpiResult,
    RecommendationRequest,
    RecommendationResponse,
    SectionInfo,
    SectionsResponse,
    WindowResult,
)

app = FastAPI(title="A3 Bau-Fenster API", version="1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── static config ──────────────────────────────────────────────────────────────
HORIZON_START = date(2026, 6, 22)   # first Monday of the 52-week search horizon
HOR_WEEKS = 52

SECTION_NAMES = [
    "Frankfurt-Ost — Offenbacher Kreuz",
    "Offenbacher Kreuz — Hanau",
    "Hanau — Aschaffenburg",
    "Aschaffenburg — Marktheidenfeld",
    "Marktheidenfeld — Würzburg",
]
SECTION_KM = ["18 km", "14 km", "22 km", "31 km", "40 km"]

# Each UI section maps to BASt station (id, direction) pairs.
# All stations are A3 Bavaria; sections 0–2 use the nearest available stations
# as traffic-pattern proxies for the Hessian stretch.
SECTION_STATIONS: dict[int, list[tuple[int, str]]] = {
    0: [(9010, "R1"), (9010, "R2")],
    1: [(9011, "R1"), (9011, "R2")],
    2: [(9033, "R1"), (9033, "R2")],
    3: [(9034, "R1"), (9034, "R2"), (9036, "R1"), (9036, "R2")],
    4: [(9040, "R1"), (9040, "R2"), (9050, "R1"), (9050, "R2")],
}

_MON_DE = ["Jan","Feb","Mär","Apr","Mai","Jun","Jul","Aug","Sep","Okt","Nov","Dez"]

# ── load model once at startup ─────────────────────────────────────────────────
_model, _meta, _df_history = load_assets()


# ── helpers ────────────────────────────────────────────────────────────────────
def _filter_to_weights(filter_mode: str) -> ScoringWeights:
    if filter_mode == "risk":
        return ScoringWeights(w_total=1.0, w_congestion=3.0, w_peak=1.0, w_logistics=0.5)
    if filter_mode == "freight":
        return ScoringWeights(w_total=1.0, w_congestion=1.5, w_peak=0.5, w_logistics=2.0)
    return ScoringWeights()  # default: minimise traffic disruption


def _to_scores(values: list[float]) -> list[int]:
    """Map lower-is-better floats to 0–100 higher-is-better ints (relative normalisation)."""
    lo, hi = min(values), max(values)
    span = hi - lo or 1.0
    return [max(3, min(99, round((1 - (v - lo) / span) * 100))) for v in values]


def _risk_label(score: int) -> str:
    return "niedrig" if score >= 68 else "mittel" if score >= 46 else "hoch"


def _fmt_date(d: date) -> str:
    return d.strftime("%d.%m.%y")


def _kw_label(d: date) -> str:
    iso = d.isocalendar()
    return f"KW {iso[1]:02d}/{str(iso[0])[2:]}"


def _window_meta(start_str: str, end_str: str) -> tuple[str, str, int, int]:
    """Return (period_str, dates_str, week_start_idx, week_span) for a window.

    start_str / end_str are the string columns from recommend_windows output,
    formatted as '%Y-%m-%d %H:%M' (e.g. '2026-08-03 00:00').
    """
    start = _dt_parse.strptime(start_str[:10], "%Y-%m-%d").date()
    end   = _dt_parse.strptime(end_str[:10],   "%Y-%m-%d").date()
    kw_s = _kw_label(start)
    kw_e = _kw_label(end)
    period = kw_s if kw_s == kw_e else f"{kw_s} – {kw_e}"
    dates = f"{_fmt_date(start)} – {_fmt_date(end)}"
    week_start = max(0, (start - HORIZON_START).days // 7)
    week_span = max(1, ((end - start).days + 1 + 6) // 7)
    return period, dates, week_start, week_span


def _month_labels() -> list[str]:
    """52-element list: non-empty label on first week of each new month."""
    labels, prev = [], -1
    for i in range(HOR_WEEKS):
        d = HORIZON_START + timedelta(weeks=i)
        m = d.month - 1  # 0-indexed
        if m != prev:
            labels.append(_MON_DE[m] + (f" '{d.strftime('%y')}" if m == 0 else ""))
            prev = m
        else:
            labels.append("")
    return labels


# ── endpoints ──────────────────────────────────────────────────────────────────
@app.get("/sections", response_model=SectionsResponse)
def get_sections():
    return SectionsResponse(
        sections=[
            SectionInfo(id=i, name=SECTION_NAMES[i], km=SECTION_KM[i])
            for i in range(5)
        ],
        horizon_start=HORIZON_START.isoformat(),
    )


@app.post("/recommendations", response_model=RecommendationResponse)
def post_recommendations(req: RecommendationRequest):
    if req.section not in SECTION_STATIONS:
        raise HTTPException(status_code=400, detail="Unknown section")

    stations = SECTION_STATIONS[req.section]
    horizon_end = HORIZON_START + timedelta(weeks=HOR_WEEKS)

    recs = get_recommendations(
        stations=stations,
        duration=ContinuousDuration(hours=req.total_hours),
        horizon_start=HORIZON_START.isoformat(),
        horizon_end=horizon_end.isoformat(),
        capacity_config=CapacityConfig(lanes_total=2, lanes_closed=1),
        scoring_weights=_filter_to_weights(req.filter),
        top_n=req.top_n,
        model=_model,
        meta=_meta,
        df_history=_df_history,
    )

    if recs is None or len(recs) == 0:
        return RecommendationResponse(windows=[], kpi=None)

    scores = _to_scores(recs["composite_score"].tolist())
    windows: list[WindowResult] = []
    for rank_0, (_, row) in enumerate(recs.iterrows()):
        period, dates, week_start, week_span = _window_meta(
            str(row["start_date"]), str(row["end_date"])
        )
        windows.append(WindowResult(
            rank=rank_0 + 1,
            period=period,
            dates=dates,
            score=scores[rank_0],
            week_start=week_start,
            week_span=week_span,
            mean_kfz_per_hour=int(row["mean_kfz_per_hour"]),
            lkw_share_pct=float(row["lkw_share_pct"]),
            congestion_pct=float(row["congestion_pct"]),
        ))

    top = windows[0]
    kpi = KpiResult(
        mean_kfz_per_hour=top.mean_kfz_per_hour,
        lkw_share_pct=top.lkw_share_pct,
        congestion_pct=top.congestion_pct,
        risk=_risk_label(top.score),
    )
    return RecommendationResponse(windows=windows, kpi=kpi)


@app.get("/heatmap-data", response_model=HeatmapResponse)
def get_heatmap(
    section: int = Query(..., ge=0, le=4),
    total_hours: int = Query(..., ge=1),
    filter: str = Query("traffic"),
):
    stations = SECTION_STATIONS[section]
    horizon_end = HORIZON_START + timedelta(weeks=HOR_WEEKS)

    burden = compute_burden(
        stations=stations,
        horizon_start=HORIZON_START.isoformat(),
        horizon_end=horizon_end.isoformat(),
        capacity_config=CapacityConfig(lanes_total=2, lanes_closed=1),
        model=_model,
        meta=_meta,
        df_history=_df_history,
    )

    ts_start = pd.Timestamp(HORIZON_START)
    burden["week_idx"] = (
        ((burden.index - ts_start) / pd.Timedelta("7D"))
        .astype(int)
        .clip(0, HOR_WEEKS - 1)
    )
    weekly = burden.groupby("week_idx")["disruption"].mean()
    mean_d = float(weekly.mean())
    disr_vals = [float(weekly.get(i, mean_d)) for i in range(HOR_WEEKS)]
    scores = _to_scores(disr_vals)

    month_labels = _month_labels()
    return HeatmapResponse(weeks=[
        HeatWeek(week_index=i, score=scores[i], month_label=month_labels[i])
        for i in range(HOR_WEEKS)
    ])
