"""
viz_recommendations.py — Visualisation for A3 construction window recommendations
===================================================================================
Four plot functions, each independently callable, plus plot_all() to run them all.

    plot_gantt()              — timeline/Gantt over search horizon
    plot_horizon_heatmap()    — DOW x Hour heatmap with window cells highlighted
    plot_summary_table()      — styled summary table with score breakdown
    plot_best_window_detail() — hour-by-hour zoom on the #1 window

Typical usage
-------------
    from recommend_windows import compute_burden, get_recommendations, load_assets
    from recommend_windows import ContinuousDuration, CapacityConfig
    from viz_recommendations import plot_all

    model, meta, df = load_assets()
    cfg = CapacityConfig(lanes_total=2, lanes_closed=1)

    burden = compute_burden([(9033,"R1"),(9033,"R2")], "2024-03-01", "2024-05-31",
                            capacity_config=cfg, model=model, meta=meta, df_history=df)
    recs   = get_recommendations([(9033,"R1"),(9033,"R2")], ContinuousDuration(72),
                                 "2024-03-01", "2024-05-31",
                                 capacity_config=cfg, model=model, meta=meta, df_history=df)
    paths  = plot_all(recs, burden, label="72h_zst9033")
"""

from __future__ import annotations

import sys
import warnings
from pathlib import Path
from typing import Optional

import matplotlib as mpl
import matplotlib.colors as mcolors
import matplotlib.dates as mdates
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd
import seaborn as sns

from recommend_windows import (
    CapacityConfig, ContinuousDuration, Duration, ScoringWeights,
    ShiftDuration, WorkConstraints, compute_burden,
    get_recommendations, load_assets,
)

warnings.filterwarnings("ignore")
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ── Aesthetics ────────────────────────────────────────────────────────────────
GERMAN_DOW    = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]
GERMAN_MONTHS = ["Jan","Feb","Mar","Apr","Mai","Jun","Jul","Aug","Sep","Okt","Nov","Dez"]

RANK_COLORS   = ["#2ca02c", "#98df8a", "#fecc5c", "#fd8d3c", "#d7191c"]   # green→red
WEEKEND_ALPHA = 0.10
CONGESTION_COLOR = "#d62728"
CAPACITY_COLOR   = "#d62728"
TRAFFIC_COLOR    = "#2171b5"
LKW_COLOR        = "#8c510a"

mpl.rcParams.update({
    "font.family":   "sans-serif",
    "axes.spines.top":   False,
    "axes.spines.right": False,
    "axes.grid":         True,
    "grid.alpha":        0.3,
    "figure.dpi":        120,
})

OUT_DIR = Path("figures/recommendations")


# ════════════════════════════════════════════════════════════════════════════════
# Shared helpers
# ════════════════════════════════════════════════════════════════════════════════

def _parse_window_ts(recs: pd.DataFrame, top_n: int) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    """Return list of (start, end) Timestamps for the top-N rows."""
    out = []
    for _, row in recs.head(top_n).iterrows():
        out.append((pd.to_datetime(row["start_date"]), pd.to_datetime(row["end_date"])))
    return out


def _shade_weekends(ax: plt.Axes, t_min: pd.Timestamp, t_max: pd.Timestamp) -> None:
    """Grey shading for Saturday–Sunday spans on a datetime x-axis."""
    cur = t_min.normalize()
    added = False
    while cur <= t_max:
        if cur.dayofweek == 5:                        # Saturday
            end_sat = cur + pd.Timedelta(days=2)
            ax.axvspan(cur, min(end_sat, t_max),
                       color="gray", alpha=WEEKEND_ALPHA, zorder=0,
                       label=("Wochenende" if not added else "_"))
            added = True
            cur += pd.Timedelta(days=2)
        else:
            cur += pd.Timedelta(days=1)


def _window_dow_hour_cells(
    start: pd.Timestamp, end: pd.Timestamp
) -> list[tuple[int, int]]:
    """All (dayofweek, hour) cells touched by the interval [start, end]."""
    cells = []
    ts = start
    while ts <= end:
        cells.append((ts.dayofweek, ts.hour))
        ts += pd.Timedelta(hours=1)
    return cells


def _color_for_score(score: float, vmin: float, vmax: float) -> str:
    norm = mcolors.Normalize(vmin=vmin, vmax=vmax)
    return mpl.cm.RdYlGn_r(norm(score))     # type: ignore[attr-defined]


def _save(fig: plt.Figure, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, bbox_inches="tight", dpi=150)
    plt.close(fig)
    print(f"  Saved: {path}")
    return path


# ════════════════════════════════════════════════════════════════════════════════
# 1. Gantt / timeline chart
# ════════════════════════════════════════════════════════════════════════════════

def plot_gantt(
    recs:    pd.DataFrame,
    burden:  pd.DataFrame,
    out_dir: Path = OUT_DIR,
    label:   str  = "",
    top_n:   int  = 5,
    figsize: tuple = (22, 9),
) -> Path:
    """
    Two-panel figure:
      TOP  — forecasted hourly Kfz curve with remaining-capacity line and
              semi-transparent coloured vertical bands for each ranked window.
      BOTTOM — Gantt bars (one row per window) with rank, score, and weekday labels.
    Shared x-axis spans the full search horizon.
    """
    windows   = _parse_window_ts(recs, top_n)
    n_windows = len(windows)
    colors    = RANK_COLORS[:n_windows]

    t_min = burden["timestamp"].min()
    t_max = burden["timestamp"].max()
    remaining_cap = float(recs["remaining_cap_veh_h"].iloc[0])

    fig, (ax_t, ax_g) = plt.subplots(
        2, 1, figsize=figsize,
        gridspec_kw={"height_ratios": [3, 1], "hspace": 0.08},
        sharex=True,
    )

    # ── traffic curve ─────────────────────────────────────────────────────────
    _shade_weekends(ax_t, t_min, t_max)

    ax_t.fill_between(burden["timestamp"], burden["kfz"],
                      alpha=0.25, color=TRAFFIC_COLOR)
    ax_t.plot(burden["timestamp"], burden["kfz"],
              color=TRAFFIC_COLOR, lw=0.9, label="Prognose Kfz/h")

    ax_t.axhline(remaining_cap, color=CAPACITY_COLOR, lw=1.8, ls="--",
                 label=f"Verbl. Kap. ({remaining_cap:,.0f} Kfz/h)")

    # ── window bands on traffic panel ─────────────────────────────────────────
    for i, (start, end) in enumerate(windows):
        rank = recs.index[i]
        score = recs.iloc[i]["composite_score"]
        ax_t.axvspan(start, end, alpha=0.22, color=colors[i], zorder=1,
                     label=f"Rang {rank}  (Score {score:.3f})")
        ax_t.axvline(start, color=colors[i], lw=1.2, alpha=0.7, zorder=2)
        ax_t.axvline(end,   color=colors[i], lw=1.2, alpha=0.7, zorder=2)

    ax_t.set_ylabel("Kfz / Stunde", fontsize=11)
    ax_t.set_ylim(bottom=0)
    ax_t.set_title(
        f"Empfohlene Bauzeitfenster — {recs['duration_label'].iloc[0]}  |  "
        f"{recs['stations_covered'].iloc[0]}  |  "
        f"Horizont: {t_min.strftime('%d.%m.%Y')} – {t_max.strftime('%d.%m.%Y')}",
        fontsize=12, pad=10,
    )
    ax_t.legend(loc="upper right", fontsize=8, ncol=3, framealpha=0.85)

    # ── Gantt bars ────────────────────────────────────────────────────────────
    ax_g.set_yticks([])
    ax_g.set_facecolor("#f8f8f8")

    for i, (start, end) in enumerate(windows):
        rank = recs.index[i]
        row  = recs.iloc[i]
        bar = ax_g.barh(
            y=i, width=end - start, left=start,
            height=0.65, color=colors[i], alpha=0.85,
            edgecolor="white", linewidth=0.8,
        )
        # Label inside bar
        mid = start + (end - start) / 2
        dow = GERMAN_DOW[start.dayofweek]
        ax_g.text(
            mid, i,
            f"#{rank}  {dow} {start.strftime('%d.%m')}  "
            f"Ø{row['mean_disruption']:.2f}  {row['congestion_hours']:d}h Stau",
            ha="center", va="center", fontsize=8, color="white" if i < 2 else "black",
            fontweight="bold",
        )

    ax_g.set_yticks(range(n_windows))
    ax_g.set_yticklabels([f"Rang {recs.index[i]}" for i in range(n_windows)], fontsize=9)
    ax_g.invert_yaxis()
    ax_g.set_xlabel("Datum", fontsize=11)

    # ── x-axis formatting ─────────────────────────────────────────────────────
    ax_g.xaxis.set_major_locator(mdates.WeekdayLocator(byweekday=mdates.MO, interval=1))
    ax_g.xaxis.set_major_formatter(mdates.DateFormatter("%d.%m."))
    ax_g.xaxis.set_minor_locator(mdates.DayLocator())
    plt.setp(ax_g.xaxis.get_majorticklabels(), rotation=45, ha="right", fontsize=8)

    stem = f"gantt_{label}" if label else "gantt"
    return _save(fig, Path(out_dir) / f"{stem}.png")


# ════════════════════════════════════════════════════════════════════════════════
# 2. DOW × Hour heatmap with window highlights
# ════════════════════════════════════════════════════════════════════════════════

def plot_horizon_heatmap(
    recs:    pd.DataFrame,
    burden:  pd.DataFrame,
    out_dir: Path = OUT_DIR,
    label:   str  = "",
    top_n:   int  = 5,
    figsize: tuple = (13, 8),
) -> Path:
    """
    Day-of-week × hour-of-day heatmap (mean forecast Kfz) computed over the
    search horizon, with the DOW×hour cells occupied by each top-N window
    drawn as coloured overlays.

    This answers "WHY was this window chosen?" — the highlighted cells sit in
    the lightest (lowest-traffic) region of the grid.
    """
    burden = burden.copy()
    burden["dow"]  = burden["timestamp"].dt.dayofweek
    burden["hour"] = burden["timestamp"].dt.hour

    pivot = (
        burden.groupby(["hour", "dow"])["kfz"]
        .mean()
        .unstack("dow")
        .reindex(columns=range(7))
    )
    pivot.columns = GERMAN_DOW

    windows = _parse_window_ts(recs, top_n)
    n_windows = len(windows)
    colors    = RANK_COLORS[:n_windows]

    fig, ax = plt.subplots(figsize=figsize)

    vmax = float(np.nanpercentile(pivot.values, 97))
    sns.heatmap(
        pivot.astype(float),
        cmap="YlOrRd", vmin=0, vmax=vmax,
        ax=ax, linewidths=0.3, linecolor="white",
        cbar_kws={"label": "Ø Kfz/h (Prognose-Horizont)", "shrink": 0.8},
        yticklabels=[f"{h:02d}:00" for h in range(24)],
    )
    ax.set_xlabel("Wochentag", fontsize=11)
    ax.set_ylabel("Stunde", fontsize=11)

    # ── period guide lines ─────────────────────────────────────────────────────
    for h in [6, 10, 16, 21]:
        ax.axhline(h, color="navy", lw=0.7, ls=":", alpha=0.5)

    # ── highlight window cells ─────────────────────────────────────────────────
    legend_patches = []
    for i, (start, end) in enumerate(windows):
        rank  = recs.index[i]
        cells = _window_dow_hour_cells(start, end)
        for (dow, hour) in cells:
            # filled overlay
            ax.add_patch(mpatches.FancyBboxPatch(
                (dow, hour), 1, 1,
                boxstyle="square,pad=0",
                facecolor=colors[i], alpha=0.40,
                edgecolor=colors[i], linewidth=0, zorder=3,
            ))
        # Outer border on first occurrence of each window (for legend clarity)
        legend_patches.append(
            mpatches.Patch(
                facecolor=colors[i], alpha=0.6,
                label=f"Rang {rank}  ({start.strftime('%a %d.%m %H:%M')})",
            )
        )

    ax.legend(
        handles=legend_patches, loc="upper left",
        bbox_to_anchor=(1.18, 1.0), fontsize=9, framealpha=0.9,
        title="Empf. Fenster", title_fontsize=9,
    )

    t_min = burden["timestamp"].min()
    t_max = burden["timestamp"].max()
    ax.set_title(
        f"Verkehrsmuster — Prognose-Horizont {t_min.strftime('%d.%m.%Y')}–{t_max.strftime('%d.%m.%Y')}\n"
        f"Farbige Zellen = DOW×Stunde-Belegung der empfohlenen Fenster",
        fontsize=11, pad=10,
    )

    stem = f"heatmap_{label}" if label else "heatmap"
    return _save(fig, Path(out_dir) / f"{stem}.png")


# ════════════════════════════════════════════════════════════════════════════════
# 3. Summary table
# ════════════════════════════════════════════════════════════════════════════════

def plot_summary_table(
    recs:    pd.DataFrame,
    out_dir: Path = OUT_DIR,
    label:   str  = "",
    figsize: Optional[tuple] = None,
) -> Path:
    """
    Styled matplotlib table showing the full score breakdown per ranked window.
    Rows are coloured green→red by composite score.
    """
    n = len(recs)
    if figsize is None:
        figsize = (20, 1.0 + 0.55 * n)

    fig, ax = plt.subplots(figsize=figsize)
    ax.axis("off")

    # ── assemble cell data ─────────────────────────────────────────────────────
    col_headers = [
        "Rang", "Start", "Ende", "Tag",
        "Score",
        "S:total", "S:Stau", "S:Peak", "S:Lkw",
        "Ø Disrupt.", "Peak Disrupt.", "Stau-Std.",
        "Σ Kfz", "Ø Kfz/h", "Peak Kfz",
        "Lkw %", "Kap. (veh/h)",
    ]
    rows = []
    for rank, row in recs.iterrows():
        rows.append([
            rank,
            row["start_date"],
            row["end_date"],
            row["start_weekday"],
            f"{row['composite_score']:.3f}",
            f"{row['score_total']:.3f}",
            f"{row['score_congestion']:.3f}",
            f"{row['score_peak']:.3f}",
            f"{row['score_logistics']:.3f}",
            f"{row['mean_disruption']:.3f}",
            f"{row['peak_disruption']:.3f}",
            int(row["congestion_hours"]),
            f"{row['total_kfz']:,.0f}",
            f"{row['mean_kfz_per_hour']:,.0f}",
            f"{row['peak_kfz']:,.0f}",
            f"{row['lkw_share_pct']:.1f}%",
            f"{int(row['remaining_cap_veh_h']):,}",
        ])

    table = ax.table(
        cellText=rows,
        colLabels=col_headers,
        loc="center",
        cellLoc="center",
    )
    table.auto_set_font_size(False)
    table.set_fontsize(8.5)
    table.scale(1.0, 1.6)

    # ── colour scheme ──────────────────────────────────────────────────────────
    score_vals = [float(recs.iloc[i]["composite_score"]) for i in range(n)]
    vmin, vmax = min(score_vals), max(score_vals) + 1e-9
    norm_fn = mcolors.Normalize(vmin=vmin, vmax=vmax)

    for (row_idx, col_idx), cell in table.get_celld().items():
        cell.set_edgecolor("#cccccc")
        if row_idx == 0:
            cell.set_facecolor("#1a1a2e")
            cell.set_text_props(color="white", fontweight="bold", fontsize=8)
        else:
            score = score_vals[row_idx - 1]
            rgba  = mpl.cm.RdYlGn_r(norm_fn(score))    # type: ignore[attr-defined]
            cell.set_facecolor((*rgba[:3], 0.35))
            if col_idx == 4:                             # Score column
                cell.set_text_props(fontweight="bold")
            # Score component columns: slightly bolder
            if col_idx in (5, 6, 7, 8):
                cell.set_text_props(color="#333333")

    # Column widths: wider for dates, narrower for numerics
    wide  = [1, 2, 2]
    for j, w in enumerate([0.4, 1.2, 1.2, 0.5, 0.65,
                             0.6, 0.6, 0.6, 0.6,
                             0.7, 0.8, 0.6,
                             0.9, 0.7, 0.8,
                             0.55, 0.8]):
        for i in range(n + 1):
            table[i, j].set_width(w / sum([0.4, 1.2, 1.2, 0.5, 0.65,
                                            0.6, 0.6, 0.6, 0.6,
                                            0.7, 0.8, 0.6,
                                            0.9, 0.7, 0.8,
                                            0.55, 0.8]))

    # ── annotations ───────────────────────────────────────────────────────────
    cap_ref = int(recs["remaining_cap_veh_h"].iloc[0])
    ranking = recs["ranking_mode"].iloc[0]
    ax.set_title(
        f"Zusammenfassung Bauzeitfenster  |  Ranking: {ranking}  |  "
        f"Verbl. Kapazitat: {cap_ref:,} Kfz/h  |  {recs['duration_label'].iloc[0]}",
        fontsize=10, pad=8,
    )
    note = (
        "Score = w_total×Ø_disrupt + w_congestion×stau_frac + w_peak×peak_disrupt + w_logistics×lkw_frac"
    )
    fig.text(0.5, 0.01, note, ha="center", fontsize=7.5, color="#555555", style="italic")

    stem = f"table_{label}" if label else "table"
    return _save(fig, Path(out_dir) / f"{stem}.png")


# ════════════════════════════════════════════════════════════════════════════════
# 4. Hour-by-hour detail for the best window
# ════════════════════════════════════════════════════════════════════════════════

def plot_best_window_detail(
    recs:     pd.DataFrame,
    burden:   pd.DataFrame,
    out_dir:  Path = OUT_DIR,
    label:    str  = "",
    duration: Optional[Duration] = None,
    figsize:  tuple = (18, 10),
) -> Path:
    """
    Zoomed hour-by-hour plot for the rank-1 recommended window.

    Upper panel  — forecasted Kfz (filled area) vs. remaining capacity (dashed
                   line).  Hours where disruption > 1 are shaded red.  Lkw
                   estimate overlaid as a stacked area.
    Lower panel  — disruption ratio per hour, with a horizontal threshold line at 1.0.
                   For ShiftDuration: non-shift hours are greyed out.
    """
    best  = recs.iloc[0]
    start = pd.to_datetime(best["start_date"])
    end   = pd.to_datetime(best["end_date"]) + pd.Timedelta(hours=1)
    rem   = float(best["remaining_cap_veh_h"])
    rank  = recs.index[0]

    wb = burden[(burden["timestamp"] >= start) & (burden["timestamp"] < end)].copy()
    if wb.empty:
        print("  WARN: burden data not found for best window — skipping detail plot")
        return Path(out_dir) / "detail_empty.png"

    ts   = wb["timestamp"]
    kfz  = wb["kfz"].values
    lkw  = wb["lkw_est"].values
    dis  = wb["disruption"].values
    cong = (wb["is_congestion"].values > 0.5)

    # For ShiftDuration: which hours are active work hours?
    active_mask = np.ones(len(wb), dtype=bool)
    if isinstance(duration, ShiftDuration):
        active_mask = np.array([duration.is_active_hour(t.hour) for t in ts])

    fig, (ax_kfz, ax_dis) = plt.subplots(
        2, 1, figsize=figsize,
        gridspec_kw={"height_ratios": [3, 1], "hspace": 0.10},
        sharex=True,
    )

    # ── upper panel: Kfz vs capacity ──────────────────────────────────────────
    ax_kfz.fill_between(ts, lkw, step="pre",
                        color=LKW_COLOR, alpha=0.55, label="Lkw-Prognose")
    ax_kfz.fill_between(ts, lkw, kfz, step="pre",
                        color=TRAFFIC_COLOR, alpha=0.45, label="Pkw-Prognose")
    ax_kfz.plot(ts, kfz, color=TRAFFIC_COLOR, lw=1.5, drawstyle="steps-pre")

    # Remaining capacity line
    ax_kfz.axhline(rem, color=CAPACITY_COLOR, lw=2.0, ls="--",
                   label=f"Verbl. Kap. {rem:,.0f} Kfz/h")

    # Congestion shading
    n_cong = int(cong.sum())
    first_cong = True
    for j, t in enumerate(ts):
        if cong[j]:
            ax_kfz.axvspan(t, t + pd.Timedelta(hours=1),
                           color=CONGESTION_COLOR, alpha=0.20, zorder=0,
                           label=("Überlastung erwartet" if first_cong else "_"))
            first_cong = False

    # Non-work-hour grey-out for shift mode
    if isinstance(duration, ShiftDuration):
        first_off = True
        for j, t in enumerate(ts):
            if not active_mask[j]:
                ax_kfz.axvspan(t, t + pd.Timedelta(hours=1),
                               color="black", alpha=0.08, zorder=0,
                               label=("Nicht-Arbeitszeit" if first_off else "_"))
                first_off = False

    # Peak marker
    peak_j = int(np.argmax(kfz))
    ax_kfz.annotate(
        f"Peak: {kfz[peak_j]:,.0f} Kfz/h",
        xy=(ts.iloc[peak_j], kfz[peak_j]),
        xytext=(ts.iloc[peak_j], kfz[peak_j] + rem * 0.12),
        arrowprops=dict(arrowstyle="->", color="black", lw=1.2),
        fontsize=9, ha="center",
    )

    # Capacity label
    if n_cong == 0:
        ax_kfz.text(
            ts.iloc[len(ts) // 2], rem * 1.03,
            "Keine Uberlastungsstunden",
            ha="center", fontsize=9, color=CAPACITY_COLOR, alpha=0.8,
        )

    ax_kfz.set_ylabel("Kfz / Stunde", fontsize=11)
    ax_kfz.set_ylim(bottom=0)
    ax_kfz.legend(loc="upper left", fontsize=9, ncol=2, framealpha=0.9)
    ax_kfz.set_title(
        f"Rang {rank} — Detailansicht: {best['start_date']} bis {best['end_date']}  "
        f"({best['duration_label']})  |  "
        f"Score {best['composite_score']:.3f}  |  "
        f"{n_cong:d} Uberlastungsstunden  |  Lkw {best['lkw_share_pct']:.1f}%",
        fontsize=11, pad=10,
    )

    # ── lower panel: disruption ratio ─────────────────────────────────────────
    ax_dis.fill_between(ts, dis, step="pre",
                        color=TRAFFIC_COLOR, alpha=0.35, label="Auslastungsgrad")
    ax_dis.plot(ts, dis, color=TRAFFIC_COLOR, lw=1.3, drawstyle="steps-pre")
    ax_dis.axhline(1.0, color=CAPACITY_COLOR, lw=1.8, ls="--",
                   label="Kapazitatsgrenze (= 1)")

    # Fill above 1.0 in red
    ax_dis.fill_between(ts, np.minimum(dis, 1.0), dis,
                        step="pre",
                        where=(dis > 1.0), color=CONGESTION_COLOR, alpha=0.4,
                        label="Uberlastungsbereich")

    # Grey non-work hours on lower panel too
    if isinstance(duration, ShiftDuration):
        for j, t in enumerate(ts):
            if not active_mask[j]:
                ax_dis.axvspan(t, t + pd.Timedelta(hours=1),
                               color="black", alpha=0.08, zorder=0)

    ax_dis.set_ylabel("Auslastungsgrad\n(1 = Kap.grenze)", fontsize=9)
    ax_dis.set_ylim(bottom=0, top=max(dis.max() * 1.2, 1.3))
    ax_dis.axhline(0.75, color="orange", lw=0.8, ls=":", alpha=0.6,
                   label="75 % Kap.")
    ax_dis.legend(loc="upper right", fontsize=8, ncol=2, framealpha=0.9)

    # ── x-axis formatting ─────────────────────────────────────────────────────
    ax_dis.xaxis.set_major_locator(mdates.HourLocator(byhour=[0, 6, 12, 18]))
    ax_dis.xaxis.set_major_formatter(mdates.DateFormatter("%a\n%d.%m\n%H:%M"))
    ax_dis.xaxis.set_minor_locator(mdates.HourLocator(byhour=range(24)))
    plt.setp(ax_dis.xaxis.get_majorticklabels(), fontsize=8)
    ax_dis.set_xlabel("Datum / Uhrzeit", fontsize=11)

    stem = f"detail_{label}" if label else "detail"
    return _save(fig, Path(out_dir) / f"{stem}.png")


# ════════════════════════════════════════════════════════════════════════════════
# 5. Orchestrator
# ════════════════════════════════════════════════════════════════════════════════

def plot_all(
    recs:     pd.DataFrame,
    burden:   pd.DataFrame,
    out_dir:  Path             = OUT_DIR,
    label:    str              = "",
    top_n:    int              = 5,
    duration: Optional[Duration] = None,
) -> dict[str, Path]:
    """
    Generate all four recommendation plots and return a {name: Path} dict.

    Parameters
    ----------
    recs     : DataFrame returned by get_recommendations()
    burden   : DataFrame returned by compute_burden() — full hourly forecast series
    out_dir  : output directory for PNGs
    label    : filename prefix (e.g. "72h_zst9033")
    top_n    : how many top windows to show in gantt/heatmap (max 5 due to palette)
    duration : original Duration object; only needed by plot_best_window_detail
               for ShiftDuration shift-hour highlighting
    """
    top_n = min(top_n, len(recs), 5)
    print(f"\n--- Generating recommendation plots -> {out_dir} ---")
    paths: dict[str, Path] = {}
    paths["gantt"]   = plot_gantt(recs, burden, out_dir, label, top_n)
    paths["heatmap"] = plot_horizon_heatmap(recs, burden, out_dir, label, top_n)
    paths["table"]   = plot_summary_table(recs, out_dir, label)
    paths["detail"]  = plot_best_window_detail(recs, burden, out_dir, label, duration)
    print(f"--- Done: {len(paths)} PNGs written ---")
    return paths


# ════════════════════════════════════════════════════════════════════════════════
# Demo / main
# ════════════════════════════════════════════════════════════════════════════════

def main() -> None:
    from recommend_windows import ScoringWeights  # already imported above, explicit here

    model, meta, df_history = load_assets()

    STATIONS = [(9033, "R1"), (9033, "R2")]
    HORIZON  = ("2024-03-01", "2024-05-31")
    cfg      = CapacityConfig(lanes_total=2, lanes_closed=1)

    # ── Scenario A: 72h continuous ────────────────────────────────────────────
    dur_a = ContinuousDuration(hours=72)
    print("\n=== Scenario A: 72h continuous closure ===")

    burden_a = compute_burden(
        STATIONS, HORIZON[0], HORIZON[1],
        capacity_config=cfg, model=model, meta=meta, df_history=df_history,
    )
    recs_a = get_recommendations(
        STATIONS, dur_a, HORIZON[0], HORIZON[1],
        capacity_config=cfg, ranking_mode="disruption",
        model=model, meta=meta, df_history=df_history,
    )
    plot_all(recs_a, burden_a, label="72h_zst9033", duration=dur_a)

    # ── Scenario B: 5-night shifts 20:00–05:00 ───────────────────────────────
    dur_b = ShiftDuration(n_days=5, shift_start=20, shift_end=5)
    print("\n=== Scenario B: 5 night shifts (20:00-05:00) ===")

    burden_b = compute_burden(
        STATIONS, HORIZON[0], HORIZON[1],
        capacity_config=cfg, model=model, meta=meta, df_history=df_history,
    )
    recs_b = get_recommendations(
        STATIONS, dur_b, HORIZON[0], HORIZON[1],
        capacity_config=cfg,
        scoring_weights=ScoringWeights(w_logistics=2.0),
        constraints=WorkConstraints(allowed_weekdays=[0, 1, 2, 3]),
        ranking_mode="disruption",
        model=model, meta=meta, df_history=df_history,
    )
    plot_all(recs_b, burden_b, label="5night_zst9033", duration=dur_b)

    # ── Scenario C: 4-station zone, 2/3 lanes closed ─────────────────────────
    ZONE = [(9033, "R1"), (9033, "R2"), (9507, "R1"), (9507, "R2")]
    cfg3 = CapacityConfig(lanes_total=3, lanes_closed=2)
    dur_c = ContinuousDuration(hours=48)
    print("\n=== Scenario C: 48h, 4-station zone, 2/3 lanes closed ===")

    burden_c = compute_burden(
        ZONE, HORIZON[0], HORIZON[1],
        capacity_config=cfg3, model=model, meta=meta, df_history=df_history,
    )
    recs_c = get_recommendations(
        ZONE, dur_c, HORIZON[0], HORIZON[1],
        capacity_config=cfg3,
        constraints=WorkConstraints(min_separation_hours=168),
        ranking_mode="disruption",
        model=model, meta=meta, df_history=df_history,
    )
    plot_all(recs_c, burden_c, label="48h_zone_3lane", duration=dur_c)


if __name__ == "__main__":
    main()
