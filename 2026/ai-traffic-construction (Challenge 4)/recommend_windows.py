"""
recommend_windows.py — A3 construction window recommendation engine
=====================================================================
Finds the best contiguous time windows for road works using LightGBM forecasts
ranked by a composite **disruption score** rather than raw vehicle counts.

Two closure modes
-----------------
  ContinuousDuration(hours=72)
      Single uninterrupted closure — slide a 72-hour block across the horizon.

  ShiftDuration(n_days=5, shift_start=20, shift_end=5)
      Night-shift work (20:00–05:00) for 5 consecutive nights — only the
      shift hours count toward the traffic burden.

Disruption scoring
------------------
Each hour during works gets a disruption ratio:

    disruption = forecasted_kfz / remaining_capacity

where remaining_capacity = full_station_capacity * (1 - lanes_closed / lanes_total).
Full capacity is estimated from the historical volume distribution (default: p97 of
observed hourly volumes — the level the road carries on its ~263 busiest hours/year).
A score > 1 indicates likely queue formation.

The composite window score combines four components (all weights configurable):

    score = w_total      * mean_disruption       (avg hourly disruption ratio)
          + w_congestion * congestion_frac        (fraction of hours with score > 1)
          + w_peak       * peak_disruption        (worst single-hour overload)
          + w_logistics  * logistics_frac         (fraction of high-freight-share hours)

Multi-station support
---------------------
Pass a list of (station_id, direction) tuples.  Disruption is computed per station
and aggregated by MAX — the worst-disrupted station governs.

Typical call
------------
    from recommend_windows import (
        get_recommendations, ContinuousDuration, ShiftDuration,
        WorkConstraints, CapacityConfig, ScoringWeights, load_assets
    )

    model, meta, df_history = load_assets()
    recs = get_recommendations(
        stations      = [(9033, "R1"), (9033, "R2")],
        duration      = ContinuousDuration(hours=72),
        horizon_start = "2024-03-01",
        horizon_end   = "2024-05-31",
        capacity_config = CapacityConfig(lanes_total=3, lanes_closed=1),
        scoring_weights = ScoringWeights(w_logistics=1.0),  # raise logistics weight
        ranking_mode  = "disruption",   # or "volume" for raw-count fallback
        model=model, meta=meta, df_history=df_history,
    )
    print(recs)
"""

from __future__ import annotations

import logging
import sys
import warnings
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Literal, Optional, Union

import numpy as np
import pandas as pd

import holidays as hol_lib

from forecast_lgbm import load_data, load_model, FEATURE_COLS, SEASON_ENC

warnings.filterwarnings("ignore")
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
log = logging.getLogger(__name__)

DATA_DIR  = Path("data_clean")
MODEL_DIR = Path("models")

GERMAN_DOW = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]

_MONTH_TO_SEASON: dict[int, str] = {
    12: "winter", 1: "winter", 2: "winter",
    3: "spring",  4: "spring",  5: "spring",
    6: "summer",  7: "summer",  8: "summer",
    9: "autumn", 10: "autumn", 11: "autumn",
}


# ════════════════════════════════════════════════════════════════════════════════
# Public data classes
# ════════════════════════════════════════════════════════════════════════════════

@dataclass
class ContinuousDuration:
    """Single uninterrupted lane/road closure.

    Parameters
    ----------
    hours : total closure length in hours (e.g. 72 for three full days)
    """
    hours: int

    @property
    def work_hours(self) -> int:
        return self.hours

    def __str__(self) -> str:
        d, h = divmod(self.hours, 24)
        parts = []
        if d:
            parts.append(f"{d}d")
        if h:
            parts.append(f"{h}h")
        return " ".join(parts) + " continuous"


@dataclass
class ShiftDuration:
    """Multi-day shift work within restricted daily hours.

    Parameters
    ----------
    n_days      : number of working days (calendar days on which a shift occurs)
    shift_start : clock hour when the shift begins (0-23, inclusive)
    shift_end   : clock hour when the shift ends (0-23, exclusive)
                  If shift_end < shift_start the shift crosses midnight (night shift).

    Example:  ShiftDuration(5, 20, 5) -> 5 nights x 9 h (20:00-05:00 each night)
    """
    n_days:      int
    shift_start: int
    shift_end:   int

    @property
    def shift_hours_per_day(self) -> int:
        if self.shift_start > self.shift_end:
            return (24 - self.shift_start) + self.shift_end
        return self.shift_end - self.shift_start

    @property
    def work_hours(self) -> int:
        return self.n_days * self.shift_hours_per_day

    def is_active_hour(self, hour: int) -> bool:
        if self.shift_start > self.shift_end:
            return hour >= self.shift_start or hour < self.shift_end
        return self.shift_start <= hour < self.shift_end

    def elapsed_hours(self) -> int:
        """Wall-clock hours from first shift-start to last shift-end."""
        if self.shift_start > self.shift_end:
            return (self.n_days - 1) * 24 + (24 - self.shift_start) + self.shift_end
        return (self.n_days - 1) * 24 + (self.shift_end - self.shift_start)

    def __str__(self) -> str:
        return (
            f"{self.n_days}x{self.shift_hours_per_day}h shift "
            f"({self.shift_start:02d}:00-{self.shift_end:02d}:00), "
            f"{self.work_hours}h total"
        )


Duration = Union[ContinuousDuration, ShiftDuration]


@dataclass
class WorkConstraints:
    """Optional restrictions on when a window is allowed to start.

    Parameters
    ----------
    earliest_start       : no window may begin before this timestamp
    latest_end           : no window may end after this timestamp
    allowed_weekdays     : list of int (0=Mon ... 6=Sun); window start must fall on one
    must_avoid_dates     : any window overlapping these calendar dates is excluded
    min_separation_hours : minimum hours between starts of consecutive ranked results;
                           0 = no deduplication
    """
    earliest_start:       Optional[pd.Timestamp] = None
    latest_end:           Optional[pd.Timestamp]  = None
    allowed_weekdays:     Optional[list[int]]      = None
    must_avoid_dates:     list[date]               = field(default_factory=list)
    min_separation_hours: int                      = 0


@dataclass
class CapacityConfig:
    """Capacity model for disruption scoring.

    Parameters
    ----------
    lanes_total          : total lanes per direction at the work zone
                           (default 2; A3 in Bavaria is mostly 3 outside urban nodes)
    lanes_closed         : lanes to be closed during works; must be < lanes_total
    capacity_percentile  : percentile of historical hourly volumes used as the
                           practical-capacity proxy.

                           Rationale: we use the p97 observed demand as a stand-in
                           for practical road capacity.  This is the volume level the
                           road carries on its ~263 busiest hours per year — the point
                           at which LOS D/E conditions (high density, near-capacity
                           flow) typically occur (cf. HBS Table 5.4).  A disruption
                           score > 1 therefore indicates that forecast demand exceeds
                           the historical peak-demand threshold, implying likely queue
                           formation.  To instead use the theoretical lane capacity
                           (~1 800 pcu/lane/h per HBS), set this to None and supply
                           manual_capacity_veh_h directly.

    manual_capacity_veh_h: optional override; if given, capacity_percentile is ignored.
                           Specify the full-direction capacity (all lanes combined) in
                           vehicles per hour.  Example: 3 lanes x 1800 = 5400.

    lkw_high_share       : Lkw fraction threshold above which an hour is flagged as a
                           high-freight period for the logistics penalty component.
                           Default 0.25 (25% heavy-goods share).
    """
    lanes_total:           int   = 2
    lanes_closed:          int   = 1
    capacity_percentile:   float = 0.97
    manual_capacity_veh_h: Optional[float] = None
    lkw_high_share:        float = 0.25

    def __post_init__(self) -> None:
        if self.lanes_closed >= self.lanes_total:
            raise ValueError(
                f"lanes_closed ({self.lanes_closed}) must be < lanes_total ({self.lanes_total})"
            )
        if self.manual_capacity_veh_h is None and not (0.5 <= self.capacity_percentile <= 1.0):
            raise ValueError("capacity_percentile must be in [0.5, 1.0]")

    @property
    def remaining_fraction(self) -> float:
        return (self.lanes_total - self.lanes_closed) / self.lanes_total


@dataclass
class ScoringWeights:
    """Weights for the four components of the composite disruption score.

    composite = w_total      * mean_disruption
              + w_congestion * congestion_frac
              + w_peak       * peak_disruption
              + w_logistics  * logistics_frac

    Component definitions
    ---------------------
    mean_disruption  : mean(forecast / remaining_capacity) over work hours;
                       0 = no traffic, 1.0 = at remaining capacity, 2.0 = 2x overload
    congestion_frac  : fraction of work hours where disruption > 1 (queues expected)
    peak_disruption  : max single-hour disruption ratio
    logistics_frac   : fraction of work hours where Lkw share > CapacityConfig.lkw_high_share

    Default rationale
    -----------------
    - w_congestion = 2.0: congestion hours penalised 2x because queue formation is a
      qualitative step-change (spillback, incident risk) beyond a linear volume increase
    - w_peak = 0.5: worst hour is partially captured in mean_disruption already
    - w_logistics = 0.5: freight disruption matters but is secondary to general flow
    """
    w_total:      float = 1.0
    w_congestion: float = 2.0
    w_peak:       float = 0.5
    w_logistics:  float = 0.5


# ════════════════════════════════════════════════════════════════════════════════
# Fast recursive forecaster  (10x speedup over the generic predict())
# ════════════════════════════════════════════════════════════════════════════════

def _fast_forecast(
    booster,
    future_idx:    pd.DatetimeIndex,
    seed_series:   dict,               # {timestamp: value} for O(1) lookup
    station_id:    int,
    direction_enc: float,              # 0=R1, 1=R2
    holiday_set:   set,
) -> np.ndarray:
    """
    Recursive multi-step hourly forecast using pre-allocated numpy arrays.

    Avoids per-step DataFrame construction by:
      - Pre-computing all calendar / cyclical features as numpy arrays upfront.
      - Maintaining a rolling buffer (numpy array) for lag and rolling-mean features.
      - Calling the native LightGBM booster on a single reusable (1 x n_features) array.

    Feature column order MUST match FEATURE_COLS in forecast_lgbm.py:
      station_id, direction_enc, season_enc, hour, dayofweek, month, week,
      is_weekend, is_holiday, sin_hour, cos_hour, sin_dow, cos_dow,
      sin_month, cos_month, lag_1h, lag_24h, lag_168h, roll_24h, roll_168h
    """
    n = len(future_idx)

    hours    = future_idx.hour.to_numpy(dtype=float)
    dows     = future_idx.dayofweek.to_numpy(dtype=float)
    months   = future_idx.month.to_numpy(dtype=float)
    weeks    = future_idx.isocalendar().week.to_numpy(dtype=float)
    is_wknd  = (dows >= 5).astype(float)
    is_hol   = np.array([float(d.date() in holiday_set) for d in future_idx])
    seasons  = np.array([float(SEASON_ENC[_MONTH_TO_SEASON[int(m)]]) for m in months])
    sin_h  = np.sin(2 * np.pi * hours  / 24);  cos_h  = np.cos(2 * np.pi * hours  / 24)
    sin_dw = np.sin(2 * np.pi * dows   / 7);   cos_dw = np.cos(2 * np.pi * dows   / 7)
    sin_mo = np.sin(2 * np.pi * months / 12);  cos_mo = np.cos(2 * np.pi * months / 12)

    buf = np.full(168 + n, np.nan)
    ts0 = future_idx[0]
    for j in range(168):
        buf[j] = seed_series.get(ts0 - pd.Timedelta(hours=168 - j), np.nan)

    X = np.empty((1, len(FEATURE_COLS)), dtype=np.float64)
    X[0, 0] = float(station_id)
    X[0, 1] = direction_enc

    results = np.empty(n, dtype=np.float64)
    for i in range(n):
        b_end = i + 168
        X[0, 2]  = seasons[i]
        X[0, 3]  = hours[i];   X[0, 4]  = dows[i];  X[0, 5]  = months[i]
        X[0, 6]  = weeks[i];   X[0, 7]  = is_wknd[i]; X[0, 8] = is_hol[i]
        X[0, 9]  = sin_h[i];   X[0, 10] = cos_h[i]
        X[0, 11] = sin_dw[i];  X[0, 12] = cos_dw[i]
        X[0, 13] = sin_mo[i];  X[0, 14] = cos_mo[i]
        X[0, 15] = buf[b_end - 1]       # lag_1h
        X[0, 16] = buf[b_end - 24]      # lag_24h
        X[0, 17] = buf[i]               # lag_168h
        X[0, 18] = np.nanmean(buf[b_end - 24: b_end])   # roll_24h
        X[0, 19] = np.nanmean(buf[i:   b_end])          # roll_168h

        pred = float(booster.predict(X)[0])
        pred = max(0.0, pred)
        buf[b_end] = pred
        results[i] = pred

    return results


# ════════════════════════════════════════════════════════════════════════════════
# Capacity estimation
# ════════════════════════════════════════════════════════════════════════════════

def _estimate_station_capacities(
    df_history:  pd.DataFrame,
    stations:    list[tuple[int, str]],
    cfg:         CapacityConfig,
) -> dict[tuple[int, str], float]:
    """
    Return full-direction capacity (all lanes, veh/h) per (station_id, direction).

    If cfg.manual_capacity_veh_h is set, that value is used for all stations.
    Otherwise the cfg.capacity_percentile-th percentile of observed hourly volumes
    is used as a practical-capacity proxy (see CapacityConfig docstring).

    Fallback: 2 000 veh/h if fewer than 100 valid hours exist for a station.
    """
    if cfg.manual_capacity_veh_h is not None:
        caps = {k: cfg.manual_capacity_veh_h for k in stations}
        log.info("  Using manual capacity: %.0f veh/h (all stations)", cfg.manual_capacity_veh_h)
        return caps

    pct = cfg.capacity_percentile * 100
    caps: dict[tuple[int, str], float] = {}
    for (sid, direction) in stations:
        sub = (
            df_history[
                (df_history["station_id"] == sid) &
                (df_history["direction"]  == direction) &
                (df_history["vehicle_count_total"].notna())
            ]["vehicle_count_total"]
            .dropna()
            .astype(float)
        )
        if len(sub) < 100:
            cap = 2000.0
            log.warning("  zst%s %s: < 100 valid hours, fallback capacity %.0f veh/h",
                        sid, direction, cap)
        else:
            cap = float(np.percentile(sub.values, pct))
            rem = cap * cfg.remaining_fraction
            log.info("  zst%s %s: p%.0f = %.0f veh/h | %d/%d lanes open -> remaining %.0f veh/h",
                     sid, direction, pct, cap, cfg.lanes_total - cfg.lanes_closed,
                     cfg.lanes_total, rem)
        caps[(sid, direction)] = cap
    return caps


# ════════════════════════════════════════════════════════════════════════════════
# Forecast generation, disruption annotation, and station aggregation
# ════════════════════════════════════════════════════════════════════════════════

def _compute_lkw_ratios(df_history: pd.DataFrame) -> pd.DataFrame:
    """Mean historical Lkw/Kfz ratio per (station, direction, hour, dayofweek)."""
    df = df_history[df_history["vehicle_count_total"] > 10].copy()
    df["lkw_ratio"] = df["vehicle_count_heavy"] / df["vehicle_count_total"]
    return (
        df.groupby(["station_id", "direction", "hour", "dayofweek"])["lkw_ratio"]
        .mean()
        .reset_index()
    )


def _generate_forecasts(
    stations:    list[tuple[int, str]],
    start:       pd.Timestamp,
    end:         pd.Timestamp,
    model,
    df_history:  pd.DataFrame,
    lkw_ratios:  pd.DataFrame,
) -> pd.DataFrame:
    """
    Forecast Kfz and estimate Lkw for every (station, direction) over [start, end).
    Returns: timestamp | station_id | direction | kfz | lkw_est
    """
    booster    = model.booster_
    future_idx = pd.date_range(start, end, freq="h", inclusive="left")
    years      = {ts.year for ts in future_idx} | {(start - pd.Timedelta(weeks=4)).year}
    holiday_set = set(hol_lib.Germany(state="BY", years=years).keys())

    def _forecast_one(sid: int, direction: str) -> pd.DataFrame:
        hist_sub = df_history[
            (df_history["station_id"] == sid) &
            (df_history["direction"]  == direction)
        ].set_index("timestamp")["vehicle_count_total"]
        seed = hist_sub.to_dict()
        kfz_arr = _fast_forecast(
            booster, future_idx, seed, sid, float(direction == "R2"), holiday_set
        )
        fc = pd.DataFrame({"timestamp": future_idx, "kfz": kfz_arr})
        fc["station_id"] = sid
        fc["direction"]  = direction
        fc["hour"]       = fc["timestamp"].dt.hour
        fc["dayofweek"]  = fc["timestamp"].dt.dayofweek
        fc = fc.merge(
            lkw_ratios[
                (lkw_ratios["station_id"] == sid) &
                (lkw_ratios["direction"]  == direction)
            ][["hour", "dayofweek", "lkw_ratio"]],
            on=["hour", "dayofweek"], how="left",
        )
        fc["lkw_ratio"].fillna(0.07, inplace=True)
        fc["lkw_est"] = fc["kfz"] * fc["lkw_ratio"]
        return fc[["timestamp", "station_id", "direction", "kfz", "lkw_est"]]

    log.info("  Forecasting %d station/direction pairs (%d hours each) in parallel ...",
             len(stations), len(future_idx))
    parts = [None] * len(stations)
    with ThreadPoolExecutor(max_workers=min(len(stations), 4)) as pool:
        futures = {pool.submit(_forecast_one, sid, d): i
                   for i, (sid, d) in enumerate(stations)}
        for fut in as_completed(futures):
            parts[futures[fut]] = fut.result()

    return pd.concat(parts, ignore_index=True)


def _add_disruption_columns(
    fc_df:             pd.DataFrame,
    station_capacities: dict[tuple[int, str], float],
    cfg:               CapacityConfig,
) -> pd.DataFrame:
    """
    Annotate each row with per-station disruption metrics.

    Adds columns:
      disruption    : kfz / remaining_capacity  (ratio; >1 = likely congestion)
      is_congestion : 1.0 if disruption > 1, else 0.0
      is_high_lkw   : 1.0 if lkw_est/kfz > cfg.lkw_high_share, else 0.0

    remaining_capacity = full_capacity * remaining_fraction
                       = full_capacity * (lanes_total - lanes_closed) / lanes_total
    """
    fc = fc_df.copy()

    cap_df = pd.DataFrame(
        [(sid, direction, cap)
         for (sid, direction), cap in station_capacities.items()],
        columns=["station_id", "direction", "_cap"],
    )
    fc = fc.merge(cap_df, on=["station_id", "direction"], how="left")
    fc["_cap"].fillna(2000.0, inplace=True)

    rem_cap = fc["_cap"] * cfg.remaining_fraction
    fc["disruption"]    = (fc["kfz"] / rem_cap.replace(0, np.nan)).fillna(0.0).clip(lower=0.0)
    fc["is_congestion"] = (fc["disruption"] > 1.0).astype(float)

    lkw_share = fc["lkw_est"] / fc["kfz"].replace(0, np.nan)
    fc["is_high_lkw"]   = (lkw_share > cfg.lkw_high_share).astype(float)

    return fc.drop(columns=["_cap"])


def _aggregate_stations(fc_df: pd.DataFrame) -> pd.DataFrame:
    """
    Per hour: MAX across all (station, direction) pairs.
    Disruption is aggregated by max so the worst-disrupted station governs
    (not the highest-volume station, which may differ when capacities differ).

    Returns: timestamp | kfz | lkw_est | disruption | is_congestion | is_high_lkw
    """
    agg_cols = ["kfz", "lkw_est", "disruption", "is_congestion", "is_high_lkw"]
    return (
        fc_df.groupby("timestamp")[agg_cols]
        .max()
        .sort_index()
        .reset_index()
    )


# ════════════════════════════════════════════════════════════════════════════════
# Constraint helpers
# ════════════════════════════════════════════════════════════════════════════════

def _overlaps_avoid_dates(start: pd.Timestamp, end: pd.Timestamp, avoid: set) -> bool:
    if not avoid:
        return False
    cur = start.normalize()
    while cur <= end.normalize():
        if cur.date() in avoid:
            return True
        cur += pd.Timedelta(days=1)
    return False


def _apply_constraints(
    candidates:  pd.DataFrame,
    constraints: WorkConstraints,
) -> pd.DataFrame:
    c = constraints
    avoid_set = set(c.must_avoid_dates) if c.must_avoid_dates else set()
    mask = pd.Series(True, index=candidates.index)

    if c.earliest_start is not None:
        mask &= candidates["start"] >= pd.Timestamp(c.earliest_start)
    if c.latest_end is not None:
        mask &= candidates["end"] <= pd.Timestamp(c.latest_end)
    if c.allowed_weekdays is not None:
        mask &= candidates["start"].dt.dayofweek.isin(set(c.allowed_weekdays))
    if avoid_set:
        overlap = candidates.apply(
            lambda r: _overlaps_avoid_dates(r["start"], r["end"], avoid_set), axis=1
        )
        mask &= ~overlap

    return candidates[mask].copy()


# ════════════════════════════════════════════════════════════════════════════════
# Window finders
# ════════════════════════════════════════════════════════════════════════════════

def _find_continuous_windows(burden: pd.DataFrame, hours: int) -> pd.DataFrame:
    """
    Vectorised O(N) sliding window using pandas rolling.
    Returns all candidate windows with both volume and disruption metrics.
    """
    ts   = burden["timestamp"]
    kfz  = burden["kfz"]
    lkw  = burden["lkw_est"]
    dis  = burden["disruption"]
    cong = burden["is_congestion"]
    hlkw = burden["is_high_lkw"]

    r_kfz  = kfz.rolling(hours).sum()
    r_lkw  = lkw.rolling(hours).sum()
    r_pkfz = kfz.rolling(hours).max()
    r_dsum = dis.rolling(hours).sum()    # total disruption (sum; /hours = mean)
    r_dpk  = dis.rolling(hours).max()   # peak disruption
    r_cong = cong.rolling(hours).sum()  # count of congestion hours
    r_hlkw = hlkw.rolling(hours).sum()  # count of high-Lkw hours

    valid = r_kfz.notna()
    idx   = ts[valid]
    return pd.DataFrame({
        "start":             (idx - pd.Timedelta(hours=hours - 1)).values,
        "end":               idx.values,
        "total_kfz":         r_kfz[valid].values,
        "peak_kfz":          r_pkfz[valid].values,
        "total_lkw":         r_lkw[valid].values,
        "total_disruption":  r_dsum[valid].values,
        "peak_disruption":   r_dpk[valid].values,
        "congestion_hours":  r_cong[valid].values,
        "high_lkw_hours":    r_hlkw[valid].values,
    }).reset_index(drop=True)


def _find_shift_windows(burden: pd.DataFrame, duration: ShiftDuration) -> pd.DataFrame:
    """
    Iterate candidate shift-start timestamps; collect active-shift-hours burden
    across n_days.  Returns candidate windows with volume and disruption metrics.
    """
    bi      = burden.set_index("timestamp")
    kd      = bi["kfz"].to_dict()
    ld      = bi["lkw_est"].to_dict()
    dd      = bi["disruption"].to_dict()
    cd      = bi["is_congestion"].to_dict()
    hd      = bi["is_high_lkw"].to_dict()

    ts_min  = burden["timestamp"].min()
    ts_max  = burden["timestamp"].max()
    elapsed = pd.Timedelta(hours=duration.elapsed_hours())
    cand_ts = pd.date_range(ts_min, ts_max - elapsed, freq="h")
    cand_ts = cand_ts[cand_ts.hour == duration.shift_start]

    results = []
    for start_ts in cand_ts:
        active: list[pd.Timestamp] = []
        for day in range(duration.n_days):
            base = start_ts + pd.Timedelta(days=day)
            for h in range(duration.shift_hours_per_day):
                active.append(base + pd.Timedelta(hours=h))

        kfz_v = np.array([kd.get(t, np.nan) for t in active], dtype=float)
        if np.isnan(kfz_v).all():
            continue

        lkw_v  = np.array([ld.get(t, np.nan) for t in active], dtype=float)
        dis_v  = np.array([dd.get(t, np.nan) for t in active], dtype=float)
        cong_v = np.array([cd.get(t, 0.0)   for t in active], dtype=float)
        hlkw_v = np.array([hd.get(t, 0.0)   for t in active], dtype=float)

        results.append({
            "start":            start_ts,
            "end":              active[-1],
            "total_kfz":        float(np.nansum(kfz_v)),
            "peak_kfz":         float(np.nanmax(kfz_v)),
            "total_lkw":        float(np.nansum(lkw_v)),
            "total_disruption": float(np.nansum(dis_v)),
            "peak_disruption":  float(np.nanmax(dis_v)),
            "congestion_hours": float(np.nansum(cong_v)),
            "high_lkw_hours":   float(np.nansum(hlkw_v)),
        })

    return pd.DataFrame(results)


# ════════════════════════════════════════════════════════════════════════════════
# Disruption scoring
# ════════════════════════════════════════════════════════════════════════════════

def _score_windows(
    candidates: pd.DataFrame,
    weights:    ScoringWeights,
    work_hours: int,
) -> pd.DataFrame:
    """
    Compute composite disruption score for each candidate window.

    Derived metrics added:
      mean_disruption  : total_disruption / work_hours
      congestion_frac  : congestion_hours / work_hours   (0-1)
      logistics_frac   : high_lkw_hours  / work_hours    (0-1)
      composite_score  : weighted combination (lower = better)
    """
    df = candidates.copy()
    df["mean_disruption"] = df["total_disruption"] / work_hours
    df["congestion_frac"] = df["congestion_hours"]  / work_hours
    df["logistics_frac"]  = df["high_lkw_hours"]    / work_hours

    df["composite_score"] = (
        weights.w_total      * df["mean_disruption"] +
        weights.w_congestion * df["congestion_frac"] +
        weights.w_peak       * df["peak_disruption"] +
        weights.w_logistics  * df["logistics_frac"]
    )
    return df


# ════════════════════════════════════════════════════════════════════════════════
# Ranking and formatting
# ════════════════════════════════════════════════════════════════════════════════

def _rank_deduplicate(
    candidates:           pd.DataFrame,
    top_n:                int,
    min_separation_hours: int,
    sort_by:              str = "composite_score",
) -> pd.DataFrame:
    """
    Sort by `sort_by` ascending, then enforce a minimum temporal gap between result
    starts so all top-N results represent genuinely distinct scheduling slots.
    """
    sorted_df = candidates.sort_values(sort_by).reset_index(drop=True)
    min_gap   = pd.Timedelta(hours=min_separation_hours)
    chosen: list = []

    for _, row in sorted_df.iterrows():
        if any(abs(row["start"] - c["start"]) < min_gap for c in chosen):
            continue
        chosen.append(row)
        if len(chosen) == top_n:
            break

    result = pd.DataFrame(chosen).reset_index(drop=True)
    result.index = result.index + 1
    result.index.name = "rank"
    return result


def _format_output(
    ranked:         pd.DataFrame,
    duration:       Duration,
    burden:         pd.DataFrame,
    stations:       list[tuple[int, str]],
    remaining_cap:  float,
    ranking_mode:   str,
    scoring_weights: ScoringWeights,
) -> pd.DataFrame:
    """Enrich the ranked result with human-readable labels and disruption breakdown."""
    df = ranked.copy()

    wh = duration.work_hours
    df["work_hours"]        = wh
    df["mean_kfz_per_hour"] = (df["total_kfz"] / wh).round(1)
    df["lkw_share_pct"]     = (df["total_lkw"] / df["total_kfz"].replace(0, np.nan) * 100).round(1)
    df["start_weekday"]     = df["start"].dt.dayofweek.map(lambda d: GERMAN_DOW[d])
    df["start_date"]        = df["start"].dt.strftime("%Y-%m-%d %H:%M")
    df["end_date"]          = df["end"].dt.strftime("%Y-%m-%d %H:%M")

    # Disruption breakdown (rounded for display)
    df["mean_disruption"]   = df["mean_disruption"].round(3)
    df["peak_disruption"]   = df["peak_disruption"].round(3)
    df["congestion_hours"]  = df["congestion_hours"].astype(int)
    df["congestion_pct"]    = (df["congestion_frac"] * 100).round(1)
    df["high_lkw_hours"]    = df["high_lkw_hours"].astype(int)
    df["logistics_pct"]     = (df["logistics_frac"] * 100).round(1)
    df["composite_score"]   = df["composite_score"].round(4)
    df["logistics_flag"]    = df["high_lkw_hours"] > 0

    # Score component breakdown for transparency
    df["score_total"]     = (scoring_weights.w_total      * df["mean_disruption"]).round(3)
    df["score_congestion"]= (scoring_weights.w_congestion * df["congestion_frac"]).round(3)
    df["score_peak"]      = (scoring_weights.w_peak       * df["peak_disruption"]).round(3)
    df["score_logistics"] = (scoring_weights.w_logistics  * df["logistics_frac"]).round(3)

    # Volume-rank among the returned top-N (shows agreement/divergence with raw count)
    df["vol_rank"] = df["total_kfz"].rank(method="first").astype(int)

    # Peak traffic hour within each window
    burden_kfz = burden.set_index("timestamp")["kfz"]
    peak_hours = []
    for _, row in df.iterrows():
        window = burden_kfz[row["start"]: row["end"]]
        peak_hours.append(window.idxmax().strftime("%Y-%m-%d %H:%M") if not window.empty else "")
    df["peak_hour"] = peak_hours

    # Metadata
    df["remaining_cap_veh_h"] = round(remaining_cap)
    df["ranking_mode"]        = ranking_mode
    df["duration_label"]      = str(duration)
    df["stations_covered"]    = str([f"{s}{d}" for s, d in stations])

    out_cols = [
        # Identity
        "start_date", "end_date", "start_weekday", "work_hours",
        # Composite score + breakdown
        "composite_score",
        "score_total", "score_congestion", "score_peak", "score_logistics",
        # Disruption components
        "mean_disruption", "peak_disruption",
        "congestion_hours", "congestion_pct",
        # Volume
        "total_kfz", "mean_kfz_per_hour", "peak_kfz", "peak_hour", "vol_rank",
        # Logistics
        "lkw_share_pct", "high_lkw_hours", "logistics_pct", "logistics_flag",
        # Reference
        "remaining_cap_veh_h", "ranking_mode", "duration_label", "stations_covered",
    ]
    return df[out_cols]


# ════════════════════════════════════════════════════════════════════════════════
# Public API
# ════════════════════════════════════════════════════════════════════════════════

def load_assets(
    model_dir: Path = MODEL_DIR,
    data_dir:  Path = DATA_DIR,
) -> tuple:
    """Convenience loader: returns (model, meta, df_history) ready for use."""
    model, meta = load_model(model_dir)
    log.info("Model loaded: %d features, target=%s", len(meta["feature_cols"]), meta["target"])
    df_history = load_data(data_dir)
    log.info("History loaded: %d rows, last=%s", len(df_history),
             df_history["timestamp"].max().date())
    return model, meta, df_history


def compute_burden(
    stations:        list[tuple[int, str]],
    horizon_start:   str,
    horizon_end:     str,
    capacity_config: Optional[CapacityConfig]  = None,
    model                                       = None,
    meta:            Optional[dict]             = None,
    df_history:      Optional[pd.DataFrame]     = None,
) -> pd.DataFrame:
    """
    Return the aggregated hourly forecast burden with disruption scores.

    This is the same 'burden' DataFrame that get_recommendations() uses internally.
    Call this once and pass the result to viz_recommendations.plot_all() to avoid
    running the LightGBM forecast a second time.

    Returns: timestamp | kfz | lkw_est | disruption | is_congestion | is_high_lkw
    """
    if model is None or meta is None or df_history is None:
        model, meta, df_history = load_assets()
    if capacity_config is None:
        capacity_config = CapacityConfig()

    hs = pd.Timestamp(horizon_start)
    he = pd.Timestamp(horizon_end)
    log.info("Computing burden %s -> %s for %s ...", hs.date(), he.date(), stations)

    station_capacities = _estimate_station_capacities(df_history, stations, capacity_config)
    lkw_ratios         = _compute_lkw_ratios(df_history)
    fc_df              = _generate_forecasts(stations, hs, he, model, df_history, lkw_ratios)
    fc_df              = _add_disruption_columns(fc_df, station_capacities, capacity_config)
    return _aggregate_stations(fc_df)


def get_recommendations(
    stations:        list[tuple[int, str]],
    duration:        Duration,
    horizon_start:   str,
    horizon_end:     str,
    constraints:     Optional[WorkConstraints]  = None,
    capacity_config: Optional[CapacityConfig]   = None,
    scoring_weights: Optional[ScoringWeights]   = None,
    ranking_mode:    Literal["disruption", "volume"] = "disruption",
    top_n:           int                         = 10,
    min_sep_hours:   Optional[int]               = None,
    model                                        = None,
    meta:            Optional[dict]              = None,
    df_history:      Optional[pd.DataFrame]      = None,
    burden:          Optional[pd.DataFrame]      = None,
) -> pd.DataFrame:
    """
    Find the best time windows to schedule road construction.

    Parameters
    ----------
    stations        : list of (station_id, direction) tuples covering the work zone
    duration        : ContinuousDuration or ShiftDuration
    horizon_start   : ISO date string for start of search period
    horizon_end     : ISO date string for end of search period
    constraints     : WorkConstraints (optional)
    capacity_config : CapacityConfig — lane count, capacity estimation method,
                      Lkw threshold (default: 2 lanes, 1 closed, p97 capacity)
    scoring_weights : ScoringWeights — component weights for composite score
                      (default: 1.0 / 2.0 / 0.5 / 0.5)
    ranking_mode    : "disruption" (default) or "volume" (raw Kfz count fallback)
    top_n           : number of recommendations to return
    min_sep_hours   : minimum hours between result starts (deduplication);
                      defaults to duration.work_hours (non-overlapping)
    model / meta / df_history : pre-loaded assets; loaded automatically if None

    Returns
    -------
    Ranked DataFrame (index = rank 1..top_n).  Key columns:
        composite_score, score_total, score_congestion, score_peak, score_logistics
        mean_disruption, peak_disruption, congestion_hours, congestion_pct
        total_kfz, peak_kfz, lkw_share_pct, high_lkw_hours, logistics_flag
        remaining_cap_veh_h  — capacity assumption used
        vol_rank             — volume-based rank within the returned top-N
    """
    if model is None or meta is None or df_history is None:
        model, meta, df_history = load_assets()
    if constraints     is None: constraints     = WorkConstraints()
    if capacity_config is None: capacity_config = CapacityConfig()
    if scoring_weights is None: scoring_weights = ScoringWeights()
    if min_sep_hours   is None: min_sep_hours   = duration.work_hours

    hs = pd.Timestamp(horizon_start)
    he = pd.Timestamp(horizon_end)

    log.info("=== Window Recommendation ===")
    log.info("Stations  : %s", stations)
    log.info("Duration  : %s", duration)
    log.info("Horizon   : %s -> %s", hs.date(), he.date())
    log.info("Lanes     : %d total, %d closed (%.0f%% remaining capacity)",
             capacity_config.lanes_total, capacity_config.lanes_closed,
             capacity_config.remaining_fraction * 100)
    log.info("Ranking   : %s", ranking_mode)

    # ── 1. Estimate capacities (fast — no forecasting) ───────────────────────
    log.info("Estimating station capacities ...")
    station_capacities = _estimate_station_capacities(df_history, stations, capacity_config)
    remaining_cap_ref  = min(
        cap * capacity_config.remaining_fraction
        for cap in station_capacities.values()
    )

    # ── 2. Forecast + annotate disruption (skip if burden pre-computed) ──────
    if burden is None:
        lkw_ratios = _compute_lkw_ratios(df_history)
        fc_df      = _generate_forecasts(stations, hs, he, model, df_history, lkw_ratios)
        fc_df      = _add_disruption_columns(fc_df, station_capacities, capacity_config)
        burden     = _aggregate_stations(fc_df)
        log.info("Forecast ready: %d hourly burden rows "
                 "(max Kfz=%.0f, max disruption=%.2f, mean disruption=%.2f)",
                 len(burden), burden["kfz"].max(),
                 burden["disruption"].max(), burden["disruption"].mean())
    else:
        log.info("Using pre-computed burden (%d rows).", len(burden))

    # ── 3. Generate candidate windows ────────────────────────────────────────
    if isinstance(duration, ContinuousDuration):
        candidates = _find_continuous_windows(burden, duration.hours)
    else:
        candidates = _find_shift_windows(burden, duration)
    log.info("Candidates before constraints: %d", len(candidates))

    # ── 4. Score windows ──────────────────────────────────────────────────────
    candidates = _score_windows(candidates, scoring_weights, duration.work_hours)

    # Add volume rank across all candidates for reference (used in format step)
    candidates["_full_vol_rank"] = candidates["total_kfz"].rank(method="first").astype(int)

    # ── 5. Apply constraints ──────────────────────────────────────────────────
    candidates = _apply_constraints(candidates, constraints)
    log.info("Candidates after constraints : %d", len(candidates))

    if candidates.empty:
        log.warning("No valid windows found — check horizon, constraints, or data coverage.")
        return pd.DataFrame()

    # ── 6. Rank and deduplicate ───────────────────────────────────────────────
    sort_col = "composite_score" if ranking_mode == "disruption" else "total_kfz"
    ranked   = _rank_deduplicate(candidates, top_n, min_sep_hours, sort_by=sort_col)

    # ── 7. Format output ──────────────────────────────────────────────────────
    return _format_output(
        ranked, duration, burden, stations,
        remaining_cap=remaining_cap_ref,
        ranking_mode=ranking_mode,
        scoring_weights=scoring_weights,
    )


# ════════════════════════════════════════════════════════════════════════════════
# Demo / main
# ════════════════════════════════════════════════════════════════════════════════

def _print_disruption_table(df: pd.DataFrame, title: str) -> None:
    print(f"\n{'='*90}")
    print(f"  {title}")
    print(f"{'='*90}")
    if df.empty:
        print("  (no results)")
        return
    show = df[[
        "start_date", "end_date", "start_weekday",
        "composite_score", "mean_disruption", "peak_disruption",
        "congestion_hours", "high_lkw_hours",
        "total_kfz", "lkw_share_pct",
    ]].copy()
    show.columns = [
        "Start", "Ende", "Tag",
        "Score", "Ø Disrupt.", "Peak Disrupt.",
        "Stau-Std.", "Lkw-Std.",
        "Sigma Kfz", "Lkw %",
    ]
    print(show.to_string(float_format="{:.3f}".format))
    print()


def _print_score_breakdown(df: pd.DataFrame, title: str) -> None:
    """Print the 4-component score breakdown per window."""
    print(f"\n  Score breakdown — {title}")
    print(f"  {'Rank':<5} {'Start':<18} {'Score':>6} = {'total':>6} + {'congest':>7} + {'peak':>6} + {'logist':>7}   cap={df['remaining_cap_veh_h'].iloc[0]:,.0f} veh/h remaining")
    for rank, row in df.iterrows():
        print(f"  {rank:<5} {row['start_date']:<18} {row['composite_score']:>6.3f} = "
              f"{row['score_total']:>6.3f} + {row['score_congestion']:>7.3f} + "
              f"{row['score_peak']:>6.3f} + {row['score_logistics']:>7.3f}   "
              f"(vol_rank={row['vol_rank']})")


def main() -> None:
    model, meta, df_history = load_assets()

    HORIZON       = ("2024-03-01", "2024-05-31")
    STATIONS_BOTH = [(9033, "R1"), (9033, "R2")]
    MULTI_ZONE    = [(9033, "R1"), (9033, "R2"), (9507, "R1"), (9507, "R2")]

    # ── Example 1: disruption ranking vs volume ranking (same scenario) ───────
    log.info("\n--- Example 1a: 72h continuous — ranked by DISRUPTION ---")
    cfg_default = CapacityConfig(lanes_total=2, lanes_closed=1)   # 50% capacity remains
    rec_dis = get_recommendations(
        stations=STATIONS_BOTH, duration=ContinuousDuration(hours=72),
        horizon_start=HORIZON[0], horizon_end=HORIZON[1],
        capacity_config=cfg_default,
        ranking_mode="disruption",
        model=model, meta=meta, df_history=df_history,
    )
    _print_disruption_table(rec_dis, "Top 10 — 72h Vollsperrung: Disruption-Ranking  zst9033 R1+R2")
    _print_score_breakdown(rec_dis, "72h / disruption")

    log.info("\n--- Example 1b: same, ranked by VOLUME (fallback) ---")
    rec_vol = get_recommendations(
        stations=STATIONS_BOTH, duration=ContinuousDuration(hours=72),
        horizon_start=HORIZON[0], horizon_end=HORIZON[1],
        capacity_config=cfg_default,
        ranking_mode="volume",
        model=model, meta=meta, df_history=df_history,
    )
    _print_disruption_table(rec_vol, "Top 10 — 72h Vollsperrung: Volumen-Ranking  zst9033 R1+R2")

    # ── Example 2: sensitivity — 1 lane closed vs 2 lanes closed ─────────────
    log.info("\n--- Example 2: sensitivity — 2 of 3 lanes closed (A3 3-lane section) ---")
    cfg_3lane_2closed = CapacityConfig(lanes_total=3, lanes_closed=2)  # 33% capacity remains
    rec_2closed = get_recommendations(
        stations=STATIONS_BOTH, duration=ContinuousDuration(hours=72),
        horizon_start=HORIZON[0], horizon_end=HORIZON[1],
        capacity_config=cfg_3lane_2closed,
        ranking_mode="disruption",
        model=model, meta=meta, df_history=df_history,
    )
    _print_disruption_table(
        rec_2closed,
        "Top 10 — 72h, 2/3 Fahrspuren gesperrt (33% verbleibende Kap.)  zst9033 R1+R2",
    )
    _print_score_breakdown(rec_2closed, "72h / 2-of-3 lanes closed")

    # ── Example 3: night shifts — shows logistics penalty ────────────────────
    log.info("\n--- Example 3: 5x night shifts, logistics penalty raised ---")
    heavy_logistics_weights = ScoringWeights(
        w_total=1.0, w_congestion=2.0, w_peak=0.5, w_logistics=2.0   # Lkw weight doubled
    )
    rec_night = get_recommendations(
        stations=STATIONS_BOTH,
        duration=ShiftDuration(n_days=5, shift_start=20, shift_end=5),
        horizon_start=HORIZON[0], horizon_end=HORIZON[1],
        capacity_config=cfg_default,
        scoring_weights=heavy_logistics_weights,
        constraints=WorkConstraints(allowed_weekdays=[0, 1, 2, 3]),
        ranking_mode="disruption",
        model=model, meta=meta, df_history=df_history,
    )
    _print_disruption_table(rec_night,
                            "Top 10 — 5 Nachteinsaetze 20:00-05:00 (Lkw-Gewicht x2)  zst9033 R1+R2")
    _print_score_breakdown(rec_night, "5-night shifts / high logistics weight")

    # ── Example 4: multi-station work zone ───────────────────────────────────
    log.info("\n--- Example 4: multi-station work zone 9033+9507, 48h ---")
    rec_zone = get_recommendations(
        stations=MULTI_ZONE, duration=ContinuousDuration(hours=48),
        horizon_start=HORIZON[0], horizon_end=HORIZON[1],
        capacity_config=cfg_default,
        constraints=WorkConstraints(min_separation_hours=168),
        ranking_mode="disruption",
        model=model, meta=meta, df_history=df_history,
    )
    _print_disruption_table(rec_zone,
                            "Top 10 — 48h Bauzone zst9033+9507 (beide Richtungen)")
    _print_score_breakdown(rec_zone, "48h multi-station zone")


if __name__ == "__main__":
    main()
