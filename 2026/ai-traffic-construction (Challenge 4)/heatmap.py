"""
heatmap.py — A3 Autobahn traffic temporal heatmaps
====================================================
Reads  data_clean/  (output of clean_data.py) and writes PNGs to  figures/.

Four heatmap types
------------------
1. plot_hour_dow      Hour-of-day (y) × Day-of-week (x)   — commuter rhythm
2. plot_week_hour     Week-of-year (x) × Hour-of-day (y)  — seasonal + daily
3. plot_month_dow     Month (x) × Day-of-week (y)          — seasonal/weekly
4. plot_station_hour  Station (y) × Hour (x)               — route comparison

Each function
  · returns the matplotlib Figure (for notebooks / further customisation)
  · saves a PNG to  out_dir/

Call pattern
------------
  df = load_data()
  plot_hour_dow(df, station_id=9010, direction="R1")
  plot_hour_dow(df, station_id=9010, direction="R1", normalize=True)
  generate_all(df)                # batch: every station × direction × metric
"""

import logging
import sys
import warnings
from pathlib import Path
from typing import Optional

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd
import seaborn as sns

# Windows CP1252 safety
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

warnings.filterwarnings("ignore")
logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
log = logging.getLogger(__name__)

# ── paths ─────────────────────────────────────────────────────────────────────
DATA_DIR   = Path("data_clean")
FIGURE_DIR = Path("figures")

# ── German axis labels ────────────────────────────────────────────────────────
DOW_LABELS   = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]
MONTH_LABELS = [
    "Jan", "Feb", "Mär", "Apr", "Mai", "Jun",
    "Jul", "Aug", "Sep", "Okt", "Nov", "Dez",
]
HOUR_LABELS = [f"{h:02d}:00" for h in range(24)]

# Traffic-period boundary lines (hours 0-23 index, drawn as axhline)
_PERIOD_LINES = [6, 10, 16, 21]   # Nacht | Morgen | Tag | Abend | Nacht

# ── per-metric config ─────────────────────────────────────────────────────────
METRIC_META = {
    "vehicle_count_total": dict(
        label      = "Ø Kfz / Stunde",
        label_norm = "Normiert (Zeilenmaximum = 1,0)",
        cmap       = "YlOrRd",
        short      = "Kfz",
        title_word = "Gesamtverkehr (Kfz)",
    ),
    "vehicle_count_heavy": dict(
        label      = "Ø Lkw / Stunde",
        label_norm = "Normiert (Zeilenmaximum = 1,0)",
        cmap       = "Blues",
        short      = "Lkw",
        title_word = "Schwerverkehr (Lkw)",
    ),
}

# ── global matplotlib style ───────────────────────────────────────────────────
plt.rcParams.update({
    "figure.dpi": 100,
    "font.family": "sans-serif",
    "font.size": 10,
    "axes.titlesize": 12,
    "axes.labelsize": 10,
    "xtick.labelsize": 9,
    "ytick.labelsize": 9,
    "figure.facecolor": "white",
    "axes.facecolor": "white",
})
sns.set_theme(style="white", font_scale=1.0)


# ════════════════════════════════════════════════════════════════════════════════
# Data loading & helpers
# ════════════════════════════════════════════════════════════════════════════════

def load_data(data_dir: Path = DATA_DIR) -> pd.DataFrame:
    """
    Load cleaned parquet, convert categoricals to plain types, and drop
    the 1,486 'u' (implausible) rows from zst9050/2023.
    """
    df = pd.read_parquet(data_dir)

    # Drop gap-fill rows (vehicle_count_total is NaN) — there are none in this
    # dataset, but kept for robustness if new data is added later.
    df = df[df["vehicle_count_total"].notna()].copy()

    # Drop implausible-flagged hours
    df = df[df["quality_flag"].astype(str) != "u"].copy()

    # Ensure plain Python types for easy groupby / comparisons
    for col in ("direction", "quality_flag", "season", "day_type"):
        if col in df.columns:
            df[col] = df[col].astype(str)

    df["station_id"] = df["station_id"].astype(int)
    df["year"]       = df["year"].astype(int)
    df["hour"]       = df["hour"].astype(int)
    df["week"]       = df["week"].astype(int)
    df["dayofweek"]  = df["dayofweek"].astype(int)
    df["month"]      = df["month"].astype(int)

    return df


def _filter(
    df: pd.DataFrame,
    station_id: Optional[int]  = None,
    direction:  Optional[str]  = None,
    years:      Optional[list] = None,
) -> pd.DataFrame:
    mask = pd.Series(True, index=df.index)
    if station_id is not None:
        mask &= df["station_id"] == station_id
    if direction is not None:
        mask &= df["direction"] == direction
    if years is not None:
        mask &= df["year"].isin(years)
    return df[mask]


def _normalize_rows(pivot: pd.DataFrame) -> pd.DataFrame:
    """Divide each row by its maximum value (0–1 scale per row)."""
    row_max = pivot.max(axis=1).replace(0, np.nan)
    return pivot.div(row_max, axis=0)


def _yr_tag(df_sub: pd.DataFrame) -> str:
    """'2018' or '2018-2023' depending on span in data subset."""
    years = sorted(df_sub["year"].unique())
    return f"{years[0]}" if len(years) == 1 else f"{years[0]}-{years[-1]}"


def _dir_label(direction: str) -> str:
    return f"Richtung {direction}"


def _save(fig: plt.Figure, path: Path, dpi: int = 150) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=dpi, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    log.info("  saved  %s", path.name)


# ════════════════════════════════════════════════════════════════════════════════
# Shared heatmap renderer
# ════════════════════════════════════════════════════════════════════════════════

def _render_heatmap(
    pivot:       pd.DataFrame,
    title:       str,
    xlabel:      str,
    ylabel:      str,
    cbar_label:  str,
    cmap:        str,
    figsize:     tuple,
    normalize:   bool       = False,
    period_lines: bool      = False,   # draw traffic-period guide lines on hour axis
    xticklabels  = True,
    yticklabels  = True,
    xtick_step:  int        = 1,
) -> plt.Figure:
    """
    Core seaborn heatmap wrapper.  Handles:
      · vmin / vmax anchoring (always starts at 0)
      · colourbar formatting
      · optional traffic-period guide lines
      · x-tick thinning for wide pivots
    """
    fig, ax = plt.subplots(figsize=figsize)

    vmin = 0.0
    vmax = 1.0 if normalize else None    # let seaborn auto-scale raw values

    # pandas nullable Float64 -> numpy float64 (seaborn pcolormesh requires it)
    plot_data = pivot.astype(float)

    # Mask NaN cells (drawn in light grey, not with the colormap 0 colour)
    mask = plot_data.isna()

    sns.heatmap(
        plot_data,
        ax           = ax,
        cmap         = cmap,
        mask         = mask,
        vmin         = vmin,
        vmax         = vmax,
        linewidths   = 0.3,
        linecolor    = "#f5f5f5",
        annot        = False,
        cbar_kws     = {
            "label":  cbar_label,
            "shrink": 0.80,
            "pad":    0.02,
            "aspect": 30,
        },
        xticklabels  = xticklabels,
        yticklabels  = yticklabels,
    )

    # Thin x-tick labels for wide heatmaps
    if xtick_step > 1:
        for i, tick in enumerate(ax.xaxis.get_ticklabels()):
            tick.set_visible(i % xtick_step == 0)

    # Traffic-period guide lines (on hour axis = y axis here)
    if period_lines:
        for h in _PERIOD_LINES:
            ax.axhline(h, color="#555555", linewidth=0.8, linestyle="--", alpha=0.5)

    # Weekend shading for DOW columns (works when cols are Mo…So)
    col_labels = list(pivot.columns)
    if col_labels == DOW_LABELS:
        for i, lbl in enumerate(col_labels):
            if lbl in ("Sa", "So"):
                ax.axvspan(i, i + 1, color="#d0e8ff", alpha=0.25, zorder=0)

    ax.set_title(title,  fontsize=12, fontweight="bold", pad=12)
    ax.set_xlabel(xlabel, labelpad=8,  fontsize=10)
    ax.set_ylabel(ylabel, labelpad=8,  fontsize=10)
    ax.tick_params(axis="both", labelsize=9)

    # Rotate x tick labels if many
    n_xcols = pivot.shape[1]
    rotation = 0 if n_xcols <= 12 else 90
    plt.setp(ax.get_xticklabels(), rotation=rotation, ha="right" if rotation else "center")
    plt.setp(ax.get_yticklabels(), rotation=0)

    plt.tight_layout(pad=1.5)
    return fig


# ════════════════════════════════════════════════════════════════════════════════
# 1. Hour-of-day × Day-of-week
# ════════════════════════════════════════════════════════════════════════════════

def plot_hour_dow(
    df:          pd.DataFrame,
    station_id:  int,
    direction:   str,
    metric:      str        = "vehicle_count_total",
    normalize:   bool       = False,
    out_dir:     Path       = FIGURE_DIR,
    years:       Optional[list] = None,
) -> Optional[plt.Figure]:
    """
    Hour-of-day (rows 00:00–23:00) × Day-of-week (cols Mo–So).
    Shows the classic commuter rush and weekend shift.
    normalize=True scales each hour-row to its own maximum.
    """
    meta = METRIC_META[metric]
    sub  = _filter(df, station_id, direction, years)
    if sub.empty:
        log.warning("No data: station=%s direction=%s", station_id, direction)
        return None

    pivot = (
        sub.groupby(["hour", "dayofweek"])[metric]
        .mean()
        .unstack("dayofweek")
        .reindex(columns=range(7))     # ensure Mo=0 … So=6 even if sparse
    )
    pivot.columns = DOW_LABELS
    pivot.index   = [f"{h:02d}:00" for h in pivot.index]

    cbar_label = meta["label_norm" if normalize else "label"]
    if normalize:
        pivot = _normalize_rows(pivot)

    yr   = _yr_tag(sub)
    norm_tag = " (normiert)" if normalize else ""
    title = (
        f"Stundenprofil nach Wochentag{norm_tag}\n"
        f"{meta['title_word']}  ·  Zst {station_id}  ·  {_dir_label(direction)}  ·  {yr}"
    )
    fig = _render_heatmap(
        pivot, title,
        xlabel       = "Wochentag",
        ylabel       = "Stunde",
        cbar_label   = cbar_label,
        cmap         = meta["cmap"],
        figsize      = (9, 8),
        normalize    = normalize,
        period_lines = True,
    )

    norm_sfx = "_norm" if normalize else ""
    fname    = f"heatmap_hour_dow_zst{station_id}_{direction}_{meta['short']}{norm_sfx}.png"
    _save(fig, out_dir / fname)
    return fig


# ════════════════════════════════════════════════════════════════════════════════
# 2. Week-of-year × Hour-of-day
# ════════════════════════════════════════════════════════════════════════════════

def plot_week_hour(
    df:          pd.DataFrame,
    station_id:  int,
    direction:   str,
    metric:      str        = "vehicle_count_total",
    normalize:   bool       = False,
    out_dir:     Path       = FIGURE_DIR,
    years:       Optional[list] = None,
) -> Optional[plt.Figure]:
    """
    Week-of-year (cols KW01–KW52) × Hour-of-day (rows 00:00–23:00).
    Reveals summer holidays, Christmas troughs, and seasonal rhythm.
    normalize=True scales each hour-row to its weekly maximum.
    """
    meta = METRIC_META[metric]
    sub  = _filter(df, station_id, direction, years)
    if sub.empty:
        log.warning("No data: station=%s direction=%s", station_id, direction)
        return None

    pivot = (
        sub.groupby(["hour", "week"])[metric]
        .mean()
        .unstack("week")
        .reindex(columns=range(1, 53))  # KW01–KW52
    )
    pivot.index   = [f"{h:02d}:00" for h in pivot.index]
    pivot.columns = [f"KW{w:02d}" for w in pivot.columns]

    cbar_label = meta["label_norm" if normalize else "label"]
    if normalize:
        pivot = _normalize_rows(pivot)

    yr   = _yr_tag(sub)
    norm_tag = " (normiert)" if normalize else ""
    title = (
        f"Jahresverlauf: Woche x Stunde{norm_tag}\n"
        f"{meta['title_word']}  ·  Zst {station_id}  ·  {_dir_label(direction)}  ·  {yr}"
    )
    fig = _render_heatmap(
        pivot, title,
        xlabel       = "Kalenderwoche",
        ylabel       = "Stunde",
        cbar_label   = cbar_label,
        cmap         = meta["cmap"],
        figsize      = (20, 7),
        normalize    = normalize,
        period_lines = True,
        xtick_step   = 4,              # show every 4th week label
    )

    norm_sfx = "_norm" if normalize else ""
    fname    = f"heatmap_week_hour_zst{station_id}_{direction}_{meta['short']}{norm_sfx}.png"
    _save(fig, out_dir / fname)
    return fig


# ════════════════════════════════════════════════════════════════════════════════
# 3. Month × Day-of-week
# ════════════════════════════════════════════════════════════════════════════════

def plot_month_dow(
    df:          pd.DataFrame,
    station_id:  int,
    direction:   str,
    metric:      str        = "vehicle_count_total",
    normalize:   bool       = False,
    out_dir:     Path       = FIGURE_DIR,
    years:       Optional[list] = None,
) -> Optional[plt.Figure]:
    """
    Month (cols Jan–Dez) × Day-of-week (rows Mo–So).
    Shows how weekend/weekday traffic ratio shifts through the year.
    normalize=True scales each weekday-row to its own monthly maximum.
    """
    meta = METRIC_META[metric]
    sub  = _filter(df, station_id, direction, years)
    if sub.empty:
        log.warning("No data: station=%s direction=%s", station_id, direction)
        return None

    pivot = (
        sub.groupby(["dayofweek", "month"])[metric]
        .mean()
        .unstack("month")
        .reindex(index=range(7), columns=range(1, 13))
    )
    pivot.index   = DOW_LABELS
    pivot.columns = MONTH_LABELS

    cbar_label = meta["label_norm" if normalize else "label"]
    if normalize:
        pivot = _normalize_rows(pivot)

    yr   = _yr_tag(sub)
    norm_tag = " (normiert)" if normalize else ""
    title = (
        f"Monat x Wochentag{norm_tag}\n"
        f"{meta['title_word']}  ·  Zst {station_id}  ·  {_dir_label(direction)}  ·  {yr}"
    )
    fig = _render_heatmap(
        pivot, title,
        xlabel       = "Monat",
        ylabel       = "Wochentag",
        cbar_label   = cbar_label,
        cmap         = meta["cmap"],
        figsize      = (11, 5),
        normalize    = normalize,
        period_lines = False,
    )

    norm_sfx = "_norm" if normalize else ""
    fname    = f"heatmap_month_dow_zst{station_id}_{direction}_{meta['short']}{norm_sfx}.png"
    _save(fig, out_dir / fname)
    return fig


# ════════════════════════════════════════════════════════════════════════════════
# 4. Station × Hour  (route comparison)
# ════════════════════════════════════════════════════════════════════════════════

def plot_station_hour(
    df:          pd.DataFrame,
    direction:   str        = "R1",
    metric:      str        = "vehicle_count_total",
    normalize:   bool       = False,
    out_dir:     Path       = FIGURE_DIR,
    years:       Optional[list] = None,
    stations:    Optional[list] = None,
) -> Optional[plt.Figure]:
    """
    Station (rows, sorted by mean traffic desc.) × Hour (cols 00:00–23:00).
    Compares the daily shape and volume of every counting station in one view.
    normalize=True scales each station-row to its own hourly peak, making
    the *shape* of the daily profile comparable independent of absolute volume.
    """
    meta = METRIC_META[metric]
    sub  = _filter(df, station_id=None, direction=direction, years=years)
    if stations is not None:
        sub = sub[sub["station_id"].isin(stations)]
    if sub.empty:
        log.warning("No data for direction=%s", direction)
        return None

    pivot = (
        sub.groupby(["station_id", "hour"])[metric]
        .mean()
        .unstack("hour")
        .reindex(columns=range(24))
    )
    pivot.columns = [f"{h:02d}:00" for h in pivot.columns]

    # Sort stations by mean traffic (busiest at top)
    row_means = pivot.mean(axis=1)
    pivot     = pivot.loc[row_means.sort_values(ascending=True).index]

    # Label rows as "zst XXXX"
    pivot.index = [f"zst {sid}" for sid in pivot.index]

    cbar_label = meta["label_norm" if normalize else "label"]
    if normalize:
        pivot = _normalize_rows(pivot)

    yr       = _yr_tag(sub)
    n_sta    = len(pivot)
    norm_tag = " (normiert)" if normalize else ""
    title    = (
        f"Stationsvergleich: alle Zahlstellen x Stunde{norm_tag}\n"
        f"{meta['title_word']}  ·  {_dir_label(direction)}  ·  {yr}  "
        f"·  {n_sta} Stationen (sortiert nach mittl. Verkehrsstaerke)"
    )

    fig_height = max(5, n_sta * 0.45 + 2)
    fig = _render_heatmap(
        pivot, title,
        xlabel      = "Stunde",
        ylabel      = "Zahlstelle",
        cbar_label  = cbar_label,
        cmap        = meta["cmap"],
        figsize     = (16, fig_height),
        normalize   = normalize,
        period_lines= False,         # hour is on x-axis here, not y
        xtick_step  = 2,
    )

    # Add traffic-period guide lines on x-axis (hours are columns now)
    ax = fig.axes[0]
    for h in _PERIOD_LINES:
        ax.axvline(h, color="#555555", linewidth=0.8, linestyle="--", alpha=0.45)

    norm_sfx = "_norm" if normalize else ""
    fname    = f"heatmap_station_hour_{direction}_{meta['short']}{norm_sfx}.png"
    _save(fig, out_dir / fname)
    return fig


# ════════════════════════════════════════════════════════════════════════════════
# Batch generator
# ════════════════════════════════════════════════════════════════════════════════

def generate_all(
    df:         pd.DataFrame,
    stations:   Optional[list] = None,
    directions: tuple          = ("R1", "R2"),
    metrics:    tuple          = ("vehicle_count_total", "vehicle_count_heavy"),
    normalize:  tuple          = (False, True),
    out_dir:    Path           = FIGURE_DIR,
    years:      Optional[list] = None,
) -> None:
    """
    Generate all four heatmap types for every station × direction × metric
    combination.  Runs in-process; ~0.3 s per plot.

    Parameters
    ----------
    stations    : list of station_id ints; None = all stations in df
    directions  : which directions to include
    metrics     : which metrics to plot
    normalize   : (False,) for raw only; (False,True) for both versions
    out_dir     : PNG output directory
    years       : restrict data to these years (None = all)
    """
    if stations is None:
        stations = sorted(df["station_id"].unique().tolist())

    n_total = (
        len(stations) * len(directions) * len(metrics) * len(normalize) * 3
        + len(directions) * len(metrics) * len(normalize)   # station comparison
    )
    log.info(
        "Generating %d plots — %d stations × %d dirs × %d metrics × %d norm-variants × 4 types",
        n_total, len(stations), len(directions), len(metrics), len(normalize),
    )

    done = 0
    for sid in stations:
        for direction in directions:
            for metric in metrics:
                for norm in normalize:
                    plot_hour_dow(df,  sid, direction, metric, norm, out_dir, years)
                    plot_week_hour(df, sid, direction, metric, norm, out_dir, years)
                    plot_month_dow(df, sid, direction, metric, norm, out_dir, years)
                    done += 3

    # Station comparison (all stations, per direction/metric/norm)
    for direction in directions:
        for metric in metrics:
            for norm in normalize:
                plot_station_hour(df, direction, metric, norm, out_dir, years,
                                  stations=stations)
                done += 1

    log.info("Done — %d PNGs written to %s", done, out_dir)


# ════════════════════════════════════════════════════════════════════════════════
# Main — generate everything
# ════════════════════════════════════════════════════════════════════════════════

def main() -> None:
    log.info("Loading cleaned parquet …")
    df = load_data()

    log.info(
        "Dataset: %d rows | %d stations | years %s",
        len(df),
        df["station_id"].nunique(),
        sorted(df["year"].unique().tolist()),
    )

    generate_all(
        df,
        stations   = None,        # all 32 stations
        directions = ("R1", "R2"),
        metrics    = ("vehicle_count_total", "vehicle_count_heavy"),
        normalize  = (False, True),
        out_dir    = FIGURE_DIR,
    )


if __name__ == "__main__":
    main()
