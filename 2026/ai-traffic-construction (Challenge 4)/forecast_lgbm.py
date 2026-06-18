"""
forecast_lgbm.py — LightGBM hourly traffic forecast for A3 Autobahn
=====================================================================
Reads  data_clean/  (output of clean_data.py) and trains a global
LightGBM regressor that forecasts hourly vehicle counts for any
counting station + direction on the A3.

Design notes
------------
* GLOBAL MODEL: one model covers all 32 stations.  station_id is a
  LightGBM categorical feature, so per-station level shifts are
  learned automatically without one-hot encoding.
* TIME-BASED SPLIT (no shuffle):
    Train  →  all data with timestamp  < 2023-07-01  (~2.5 years)
    Val    →  all data with timestamp ≥ 2023-07-01  (~6 months)
  The validation set contains only the 19 stations present in 2023.
  Stations that appear only in 2018 or 2022 contribute to training
  and help the model learn general road patterns.
* LAG SAFETY: the 2018 → 2022 gap is ~26 000 hours.  A naïve
  row-based shift would silently pull values from the wrong year.
  Every lag/roll is validated: if the actual timestamp distance
  between row i and row i-k does not match the expected k hours,
  the feature is set to NaN and the row is dropped from training.
* MODULARITY: add weather features by passing a weather_df with
  columns  [timestamp, station_id, <weather cols>]  to
  build_features().  Extend WEATHER_FEATURE_COLS and the merge
  inside build_features(); the rest of the pipeline is unchanged.

Public API
----------
  df         = load_data()
  feat_df    = build_features(df, target="vehicle_count_total")
  model, meta = train(feat_df)
  preds      = predict(model, meta,
                       station_id=9033, direction="R1",
                       start="2024-01-01", end="2024-01-07",
                       df_history=df)
"""

import json
import logging
import sys
import warnings
from pathlib import Path
from typing import Optional

import joblib
import lightgbm as lgb
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error

warnings.filterwarnings("ignore")
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
log = logging.getLogger(__name__)

# ── paths ─────────────────────────────────────────────────────────────────────
DATA_DIR   = Path("data_clean")
MODEL_DIR  = Path("models")
FIGURE_DIR = Path("figures")

# ── split ─────────────────────────────────────────────────────────────────────
SPLIT_DATE = pd.Timestamp("2023-07-01")

# ── targets ───────────────────────────────────────────────────────────────────
TARGET_TOTAL = "vehicle_count_total"
TARGET_HEAVY = "vehicle_count_heavy"

# ── feature groups (extend WEATHER_FEATURE_COLS to add weather inputs) ────────
CALENDAR_COLS = ["hour", "dayofweek", "month", "week", "is_weekend", "is_holiday"]
CYCLICAL_COLS = ["sin_hour", "cos_hour", "sin_dow", "cos_dow", "sin_month", "cos_month"]
ID_COLS       = ["station_id", "direction_enc", "season_enc"]
LAG_COLS      = ["lag_1h", "lag_24h", "lag_168h"]
ROLL_COLS     = ["roll_24h", "roll_168h"]
WEATHER_FEATURE_COLS: list[str] = []   # ← add weather column names here

FEATURE_COLS = ID_COLS + CALENDAR_COLS + CYCLICAL_COLS + LAG_COLS + ROLL_COLS + WEATHER_FEATURE_COLS
CAT_FEATURES  = ["station_id"]

SEASON_ENC = {"winter": 0, "spring": 1, "summer": 2, "autumn": 3}

# ── LightGBM hyperparameters ──────────────────────────────────────────────────
LGBM_PARAMS = dict(
    n_estimators        = 3000,
    learning_rate       = 0.05,
    max_depth           = 8,
    num_leaves          = 127,
    min_child_samples   = 30,
    subsample           = 0.8,
    subsample_freq      = 5,
    colsample_bytree    = 0.8,
    reg_alpha           = 0.05,
    reg_lambda          = 0.1,
    random_state        = 42,
    n_jobs              = -1,
    verbose             = -1,
)


# ════════════════════════════════════════════════════════════════════════════════
# 1.  Data loading
# ════════════════════════════════════════════════════════════════════════════════

def load_data(data_dir: Path = DATA_DIR) -> pd.DataFrame:
    """Load cleaned parquet and cast to numpy-compatible dtypes."""
    df = pd.read_parquet(data_dir)
    df = df[df["vehicle_count_total"].notna()].copy()
    df = df[df["quality_flag"].astype(str) != "u"].copy()

    df["timestamp"]   = pd.to_datetime(df["timestamp"])
    df["station_id"]  = df["station_id"].astype(int)
    df["year"]        = df["year"].astype(int)
    df["month"]       = df["month"].astype(int)
    df["week"]        = df["week"].astype(int)
    df["dayofweek"]   = df["dayofweek"].astype(int)
    df["hour"]        = df["hour"].astype(int)
    df["is_weekend"]  = df["is_weekend"].astype(bool)
    df["is_holiday"]  = df["is_holiday"].astype(bool)
    df["direction"]   = df["direction"].astype(str)
    df["season"]      = df["season"].astype(str)
    df[TARGET_TOTAL]  = df[TARGET_TOTAL].astype(float)
    df[TARGET_HEAVY]  = df[TARGET_HEAVY].astype(float)

    return df.sort_values(["station_id", "direction", "timestamp"]).reset_index(drop=True)


# ════════════════════════════════════════════════════════════════════════════════
# 2.  Feature engineering
# ════════════════════════════════════════════════════════════════════════════════

def _cyclical(series: pd.Series, period: float) -> tuple[pd.Series, pd.Series]:
    """Map a linear periodic column to (sin, cos) pair."""
    angle = 2 * np.pi * series / period
    return np.sin(angle), np.cos(angle)


def _add_lag_roll(
    grp: pd.DataFrame,
    col: str,
    lags: list[int],
    rolls: list[int],
) -> pd.DataFrame:
    """
    Compute lag and rolling-mean features for one (station, direction) group.

    Year-gap safety: after computing each row-based shift, the actual
    timestamp distance is checked against the expected number of hours.
    Any lag that spans a year gap (e.g. shift-168 at 2022-01-01 lands in
    2018-12-25) is set to NaN so the row will be dropped from training.
    """
    grp = grp.sort_values("timestamp").copy()
    ts  = grp["timestamp"]

    for k in lags:
        expected  = pd.Timedelta(hours=k)
        shifted   = grp[col].shift(k)
        valid     = (ts - ts.shift(k)) == expected
        grp[f"lag_{k}h"] = shifted.where(valid)

    for w in rolls:
        # A roll of w hours is only valid when the w-1 lag is also valid
        expected_span = pd.Timedelta(hours=w - 1)
        span_valid    = (ts - ts.shift(w - 1)) == expected_span
        rolled        = grp[col].rolling(w, min_periods=w).mean()
        grp[f"roll_{w}h"] = rolled.where(span_valid)

    return grp


def build_features(
    df:          pd.DataFrame,
    target:      str                    = TARGET_TOTAL,
    weather_df:  Optional[pd.DataFrame] = None,
) -> pd.DataFrame:
    """
    Build the full modelling feature matrix.

    Parameters
    ----------
    df          Cleaned DataFrame from load_data().
    target      Column to forecast ('vehicle_count_total' or 'vehicle_count_heavy').
    weather_df  Optional: DataFrame with columns
                  [timestamp, station_id, <weather_cols>]
                  indexed to the same hourly grid.
                  Extend WEATHER_FEATURE_COLS with the column names.

    Returns
    -------
    DataFrame with all FEATURE_COLS plus the target column.
    Rows where any lag/roll feature is NaN are dropped (~1.3% of data,
    concentrated at 2018-01-01 and 2022-01-01 starts).
    """
    log.info("Building features for target='%s' …", target)

    # ── cyclical encodings ────────────────────────────────────────────────────
    df["sin_hour"],  df["cos_hour"]  = _cyclical(df["hour"],      24)
    df["sin_dow"],   df["cos_dow"]   = _cyclical(df["dayofweek"],   7)
    df["sin_month"], df["cos_month"] = _cyclical(df["month"],      12)

    # ── ordinal encodings ─────────────────────────────────────────────────────
    df["season_enc"]    = df["season"].map(SEASON_ENC).astype(float)
    df["direction_enc"] = (df["direction"] == "R2").astype(float)
    df["is_weekend"]    = df["is_weekend"].astype(float)
    df["is_holiday"]    = df["is_holiday"].astype(float)

    # ── lag + rolling features (per station × direction) ──────────────────────
    parts = []
    groups = df.groupby(["station_id", "direction"], sort=False)
    n = groups.ngroups
    for i, ((sid, direction), grp) in enumerate(groups, 1):
        if i % 16 == 0:
            log.info("  lag/roll: %d/%d groups", i, n)
        parts.append(
            _add_lag_roll(grp, target, lags=[1, 24, 168], rolls=[24, 168])
        )
    df = pd.concat(parts, ignore_index=True)

    # ── optional weather merge ────────────────────────────────────────────────
    if weather_df is not None and WEATHER_FEATURE_COLS:
        df = df.merge(
            weather_df[["timestamp", "station_id"] + WEATHER_FEATURE_COLS],
            on=["timestamp", "station_id"],
            how="left",
        )
        log.info("Merged weather features: %s", WEATHER_FEATURE_COLS)

    # ── drop rows with any NaN in lag/roll features ───────────────────────────
    before = len(df)
    df = df.dropna(subset=LAG_COLS + ROLL_COLS).reset_index(drop=True)
    dropped = before - len(df)
    log.info(
        "Dropped %d rows with NaN lags (%.1f%%) — year-boundary warm-up rows.",
        dropped, 100 * dropped / before,
    )

    # ── final dtypes ──────────────────────────────────────────────────────────
    for col in FEATURE_COLS:
        if col in df.columns:
            df[col] = df[col].astype(float)
    df["station_id"] = df["station_id"].astype(int)   # restore int for LightGBM cat

    return df.sort_values(["station_id", "direction", "timestamp"]).reset_index(drop=True)


# ════════════════════════════════════════════════════════════════════════════════
# 3.  Train / validation split
# ════════════════════════════════════════════════════════════════════════════════

def time_split(feat_df: pd.DataFrame, split: pd.Timestamp = SPLIT_DATE):
    """
    Strict temporal split — no shuffling, no leakage.

    Train : timestamp  < split   (~2.5 non-contiguous years: 2018 full,
                                   2022 full, 2023 Jan–Jun)
    Val   : timestamp ≥ split    (~6 months: 2023 Jul–Dec, 19 stations)

    The validation set is deliberately forward-only: every training row
    occurs *before* every validation row for the same station+direction.
    """
    train = feat_df[feat_df["timestamp"] < split].copy()
    val   = feat_df[feat_df["timestamp"] >= split].copy()

    log.info("Train/val split at %s", split.date())
    log.info(
        "  Train: %8d rows | %d stations | %s -> %s",
        len(train), train["station_id"].nunique(),
        train["timestamp"].min().date(), train["timestamp"].max().date(),
    )
    log.info(
        "  Val:   %8d rows | %d stations | %s -> %s",
        len(val), val["station_id"].nunique(),
        val["timestamp"].min().date(), val["timestamp"].max().date(),
    )
    return train, val


# ════════════════════════════════════════════════════════════════════════════════
# 4.  Model training
# ════════════════════════════════════════════════════════════════════════════════

def train(
    feat_df:    pd.DataFrame,
    target:     str                  = TARGET_TOTAL,
    params:     Optional[dict]       = None,
    split:      pd.Timestamp         = SPLIT_DATE,
) -> tuple[lgb.LGBMRegressor, dict]:
    """
    Train a LightGBM regressor with early stopping on the validation set.

    Returns (fitted model, metadata dict).
    """
    train_df, val_df = time_split(feat_df, split)

    X_train = train_df[FEATURE_COLS]
    y_train = train_df[target]
    X_val   = val_df[FEATURE_COLS]
    y_val   = val_df[target]

    lgbm_params = {**LGBM_PARAMS, **(params or {})}
    model = lgb.LGBMRegressor(**lgbm_params)

    log.info("Training LightGBM (%d trees max, early stop=50) …", lgbm_params["n_estimators"])
    model.fit(
        X_train, y_train,
        eval_set          = [(X_val, y_val)],
        categorical_feature = CAT_FEATURES,
        callbacks         = [
            lgb.early_stopping(50, verbose=False),
            lgb.log_evaluation(200),
        ],
    )
    log.info("Best iteration: %d trees", model.best_iteration_)

    meta = {
        "target":        target,
        "feature_cols":  FEATURE_COLS,
        "cat_features":  CAT_FEATURES,
        "split_date":    str(split.date()),
        "n_train":       len(train_df),
        "n_val":         len(val_df),
        "best_iter":     model.best_iteration_,
        "season_enc":    SEASON_ENC,
        "weather_cols":  WEATHER_FEATURE_COLS,
    }
    return model, meta


# ════════════════════════════════════════════════════════════════════════════════
# 5.  Evaluation
# ════════════════════════════════════════════════════════════════════════════════

def mape(y_true: np.ndarray, y_pred: np.ndarray, min_actual: float = 10.0) -> float:
    """MAPE, excluding hours where actual traffic < min_actual (avoids /0 near midnight)."""
    mask  = y_true >= min_actual
    if mask.sum() == 0:
        return np.nan
    return 100 * np.mean(np.abs((y_true[mask] - y_pred[mask]) / y_true[mask]))


def evaluate(
    model:    lgb.LGBMRegressor,
    feat_df:  pd.DataFrame,
    target:   str = TARGET_TOTAL,
    split:    pd.Timestamp = SPLIT_DATE,
) -> pd.DataFrame:
    """
    Compute MAE, RMSE, MAPE on the validation set — globally and per station.

    Returns a DataFrame with one row per station + one 'ALL' aggregate row.
    """
    val_df = feat_df[feat_df["timestamp"] >= split].copy()
    val_df["_pred"] = model.predict(val_df[FEATURE_COLS]).clip(min=0)

    rows = []
    for sid, grp in val_df.groupby("station_id"):
        yt = grp[target].values
        yp = grp["_pred"].values
        rows.append({
            "station_id": int(sid),
            "n_rows":     len(grp),
            "mae":        mean_absolute_error(yt, yp),
            "rmse":       np.sqrt(mean_squared_error(yt, yp)),
            "mape":       mape(yt, yp),
        })

    # Global
    yt_all = val_df[target].values
    yp_all = val_df["_pred"].values
    rows.append({
        "station_id": "ALL",
        "n_rows":     len(val_df),
        "mae":        mean_absolute_error(yt_all, yp_all),
        "rmse":       np.sqrt(mean_squared_error(yt_all, yp_all)),
        "mape":       mape(yt_all, yp_all),
    })

    metrics_df = pd.DataFrame(rows).set_index("station_id")
    log.info("\n%s", metrics_df.to_string(float_format="{:.1f}".format))
    return metrics_df


# ════════════════════════════════════════════════════════════════════════════════
# 6.  Plots
# ════════════════════════════════════════════════════════════════════════════════

def plot_pred_vs_actual(
    model:      lgb.LGBMRegressor,
    feat_df:    pd.DataFrame,
    target:     str        = TARGET_TOTAL,
    station_id: int        = 9033,
    direction:  str        = "R1",
    split:      pd.Timestamp = SPLIT_DATE,
    n_weeks:    int        = 2,
    out_dir:    Path       = FIGURE_DIR,
) -> plt.Figure:
    """
    Plot n_weeks of predicted vs actual traffic starting from the first
    complete Monday in the validation set.
    """
    sub = feat_df[
        (feat_df["timestamp"] >= split) &
        (feat_df["station_id"] == station_id) &
        (feat_df["direction"]  == direction)
    ].copy().sort_values("timestamp")

    # Start on first Monday after split
    mondays = sub[sub["dayofweek"] == 0]["timestamp"]
    if mondays.empty:
        start_ts = sub["timestamp"].iloc[0]
    else:
        start_ts = mondays.iloc[0]
    end_ts = start_ts + pd.Timedelta(hours=24 * 7 * n_weeks)

    window = sub[(sub["timestamp"] >= start_ts) & (sub["timestamp"] < end_ts)]
    actual = window[target].values
    pred   = model.predict(window[FEATURE_COLS]).clip(min=0)
    ts     = window["timestamp"].values

    mae_w  = mean_absolute_error(actual, pred)
    rmse_w = np.sqrt(mean_squared_error(actual, pred))

    fig, ax = plt.subplots(figsize=(16, 5))
    ax.plot(ts, actual, color="#2c7bb6", linewidth=1.4,  label="Messwert (tatsächlich)", alpha=0.9)
    ax.plot(ts, pred,   color="#d7191c", linewidth=1.2,  label="LightGBM-Prognose",      alpha=0.85, linestyle="--")

    # Weekend shading
    for day_start in pd.date_range(start_ts, end_ts, freq="D"):
        if day_start.weekday() >= 5:
            ax.axvspan(day_start, day_start + pd.Timedelta(hours=24),
                       color="#e8eaf6", alpha=0.5, zorder=0)

    ax.xaxis.set_major_formatter(mdates.DateFormatter("%a %d.%m"))
    ax.xaxis.set_major_locator(mdates.DayLocator())
    plt.setp(ax.get_xticklabels(), rotation=35, ha="right", fontsize=8)
    ax.set_xlabel("Datum / Uhrzeit", labelpad=6)
    ax.set_ylabel("Kfz / Stunde", labelpad=6)
    ax.set_title(
        f"Prognose vs. Messwert — Zst {station_id} · {direction} · "
        f"{pd.Timestamp(start_ts).strftime('%d.%m.%Y')} – "
        f"{(pd.Timestamp(end_ts) - pd.Timedelta(hours=1)).strftime('%d.%m.%Y')}\n"
        f"MAE = {mae_w:.0f} Kfz/h  |  RMSE = {rmse_w:.0f} Kfz/h  "
        f"({'Wochenende schattiert' if n_weeks <= 3 else ''})",
        fontweight="bold",
    )
    ax.legend(loc="upper left", fontsize=9)
    ax.grid(axis="y", alpha=0.3)
    plt.tight_layout()

    out_dir.mkdir(parents=True, exist_ok=True)
    fname = out_dir / f"forecast_pred_actual_zst{station_id}_{direction}.png"
    fig.savefig(fname, dpi=150, bbox_inches="tight")
    log.info("Saved  %s", fname.name)
    return fig


def plot_feature_importance(
    model:   lgb.LGBMRegressor,
    out_dir: Path = FIGURE_DIR,
    top_n:   int  = 20,
) -> plt.Figure:
    """Horizontal bar chart of LightGBM gain-based feature importance."""
    importance = (
        pd.Series(model.feature_importances_, index=FEATURE_COLS, name="gain")
        .sort_values(ascending=True)
        .tail(top_n)
    )

    LABEL_MAP = {
        "lag_168h": "Lag 168h (1 Woche zurück)",
        "lag_24h":  "Lag 24h (Vortag)",
        "lag_1h":   "Lag 1h",
        "roll_168h":"Rolling-Ø 168h",
        "roll_24h": "Rolling-Ø 24h",
        "hour":     "Stunde",
        "dayofweek":"Wochentag",
        "month":    "Monat",
        "week":     "Kalenderwoche",
        "station_id":"Zählstellen-ID",
        "sin_hour": "sin(Stunde)",
        "cos_hour": "cos(Stunde)",
        "sin_dow":  "sin(Wochentag)",
        "cos_dow":  "cos(Wochentag)",
        "sin_month":"sin(Monat)",
        "cos_month":"cos(Monat)",
        "is_weekend":"Wochenende",
        "is_holiday":"Feiertag",
        "season_enc":"Jahreszeit",
        "direction_enc":"Richtung",
    }
    labels = [LABEL_MAP.get(f, f) for f in importance.index]

    fig, ax = plt.subplots(figsize=(9, max(4, top_n * 0.38)))
    bars = ax.barh(range(len(importance)), importance.values,
                   color="#4a90d9", edgecolor="white", height=0.7)
    ax.set_yticks(range(len(importance)))
    ax.set_yticklabels(labels, fontsize=9)
    ax.set_xlabel("Feature Importance (Gain)", labelpad=6)
    ax.set_title("LightGBM Feature-Wichtigkeit (Top 20, Gain)\nA3 Gesamtverkehr (Kfz)",
                 fontweight="bold", pad=10)
    ax.grid(axis="x", alpha=0.3)
    plt.tight_layout()

    out_dir.mkdir(parents=True, exist_ok=True)
    fname = out_dir / "forecast_feature_importance.png"
    fig.savefig(fname, dpi=150, bbox_inches="tight")
    log.info("Saved  %s", fname.name)
    return fig


# ════════════════════════════════════════════════════════════════════════════════
# 7.  Save / load
# ════════════════════════════════════════════════════════════════════════════════

def save_model(
    model:    lgb.LGBMRegressor,
    meta:     dict,
    out_dir:  Path = MODEL_DIR,
    name:     str  = "lgbm_traffic",
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    model_path = out_dir / f"{name}.txt"
    meta_path  = out_dir / f"{name}_meta.json"
    joblib_path = out_dir / f"{name}.joblib"

    model.booster_.save_model(str(model_path))
    with open(meta_path, "w") as f:
        json.dump(meta, f, indent=2)
    joblib.dump(model, str(joblib_path))

    log.info("Model saved  → %s  (native: %s)", joblib_path.name, model_path.name)


def load_model(
    model_dir: Path = MODEL_DIR,
    name:      str  = "lgbm_traffic",
) -> tuple[lgb.LGBMRegressor, dict]:
    joblib_path = model_dir / f"{name}.joblib"
    meta_path   = model_dir / f"{name}_meta.json"
    model = joblib.load(str(joblib_path))
    with open(meta_path) as f:
        meta = json.load(f)
    return model, meta


# ════════════════════════════════════════════════════════════════════════════════
# 8.  predict() — recursive multi-step forecaster
# ════════════════════════════════════════════════════════════════════════════════

def _build_single_row(
    ts:          pd.Timestamp,
    station_id:  int,
    direction:   str,
    lag_buf:     dict,          # {timestamp: value} lookup
    meta:        dict,
    weather_row: Optional[dict] = None,
) -> dict:
    """Build one row of features for a future timestamp."""
    is_holiday_set = meta.get("_holiday_set", set())

    def lag(h: int) -> float:
        return lag_buf.get(ts - pd.Timedelta(hours=h), np.nan)

    def roll(w: int) -> float:
        vals = [lag_buf.get(ts - pd.Timedelta(hours=i + 1), np.nan) for i in range(w)]
        vals = [v for v in vals if not np.isnan(v)]
        return float(np.mean(vals)) if vals else np.nan

    month      = ts.month
    hour       = ts.hour
    dow        = ts.dayofweek
    season_map = meta["season_enc"]
    season_str = ["winter","winter","spring","spring","spring","summer",
                  "summer","summer","autumn","autumn","autumn","winter"][month - 1]

    row = {
        "station_id":   station_id,
        "direction_enc": float(direction == "R2"),
        "hour":         float(hour),
        "dayofweek":    float(dow),
        "month":        float(month),
        "week":         float(ts.isocalendar().week),
        "is_weekend":   float(dow >= 5),
        "is_holiday":   float(ts.date() in is_holiday_set),
        "season_enc":   float(season_map[season_str]),
        "sin_hour":     float(np.sin(2 * np.pi * hour / 24)),
        "cos_hour":     float(np.cos(2 * np.pi * hour / 24)),
        "sin_dow":      float(np.sin(2 * np.pi * dow / 7)),
        "cos_dow":      float(np.cos(2 * np.pi * dow / 7)),
        "sin_month":    float(np.sin(2 * np.pi * month / 12)),
        "cos_month":    float(np.cos(2 * np.pi * month / 12)),
        "lag_1h":       lag(1),
        "lag_24h":      lag(24),
        "lag_168h":     lag(168),
        "roll_24h":     roll(24),
        "roll_168h":    roll(168),
    }
    # Weather placeholder
    for wc in meta.get("weather_cols", []):
        row[wc] = (weather_row or {}).get(wc, np.nan)

    return row


def predict(
    model:          lgb.LGBMRegressor,
    meta:           dict,
    station_id:     int,
    direction:      str,
    start:          str,
    end:            str,
    df_history:     Optional[pd.DataFrame] = None,
    weather_df:     Optional[pd.DataFrame] = None,
    data_dir:       Path = DATA_DIR,
) -> pd.DataFrame:
    """
    Recursive multi-step forecast for a single station+direction.

    For steps where the lag timestamp falls within the forecast horizon,
    previously forecasted values are used (recursive forecasting).
    For steps where the lag timestamp is in history, actual measured
    values are used — these are more accurate.

    Parameters
    ----------
    start / end     ISO date strings, e.g. "2024-01-01" / "2024-01-07"
    df_history      Historical data for lag warm-up.  If None, the cleaned
                    parquet is loaded automatically.
    weather_df      Optional weather features DataFrame (future timestamps).

    Returns
    -------
    DataFrame with columns [timestamp, station_id, direction, forecast].
    """
    import holidays as hol_lib

    future_idx = pd.date_range(start, end, freq="h", inclusive="left")
    if future_idx.empty:
        return pd.DataFrame()

    # ── load history if not supplied ─────────────────────────────────────────
    if df_history is None:
        log.info("Loading history from %s …", data_dir)
        df_history = pd.read_parquet(data_dir)
        df_history["timestamp"]  = pd.to_datetime(df_history["timestamp"])
        df_history["station_id"] = df_history["station_id"].astype(int)
        df_history["direction"]  = df_history["direction"].astype(str)
        df_history[meta["target"]] = df_history[meta["target"]].astype(float)

    hist_sub = df_history[
        (df_history["station_id"] == station_id) &
        (df_history["direction"]  == direction)
    ].set_index("timestamp")[meta["target"]].to_dict()

    # ── holiday set for all relevant years ───────────────────────────────────
    years = {ts.year for ts in future_idx} | {(pd.Timestamp(start) - pd.Timedelta(weeks=4)).year}
    holiday_set = set(hol_lib.Germany(state="BY", years=years).keys())
    meta["_holiday_set"] = holiday_set

    # ── weather lookup ────────────────────────────────────────────────────────
    weather_lookup: dict[pd.Timestamp, dict] = {}
    if weather_df is not None and meta.get("weather_cols"):
        weather_df = weather_df[
            (weather_df["station_id"] == station_id) |
            ("station_id" not in weather_df.columns)
        ].set_index("timestamp")
        for ts, row in weather_df.iterrows():
            weather_lookup[ts] = row[meta["weather_cols"]].to_dict()

    # ── recursive forecast ───────────────────────────────────────────────────
    lag_buf = dict(hist_sub)   # grows as we forecast forward
    results = []

    for ts in future_idx:
        row   = _build_single_row(ts, station_id, direction, lag_buf, meta,
                                  weather_lookup.get(ts))
        X     = pd.DataFrame([row])[FEATURE_COLS].astype(float)
        X["station_id"] = int(station_id)
        pred  = float(model.predict(X)[0])
        pred  = max(0.0, pred)

        lag_buf[ts] = pred
        results.append({"timestamp": ts, "station_id": station_id,
                         "direction": direction, "forecast": pred})

    return pd.DataFrame(results)


# ════════════════════════════════════════════════════════════════════════════════
# 9.  main()
# ════════════════════════════════════════════════════════════════════════════════

def main() -> None:
    # ── load & build features ─────────────────────────────────────────────────
    log.info("Loading data …")
    df = load_data()
    log.info("  %d rows, %d stations", len(df), df["station_id"].nunique())

    feat_df = build_features(df, target=TARGET_TOTAL)
    log.info("  Feature matrix: %d rows × %d features", len(feat_df), len(FEATURE_COLS))

    # ── train ─────────────────────────────────────────────────────────────────
    model, meta = train(feat_df, target=TARGET_TOTAL)

    # ── evaluate ──────────────────────────────────────────────────────────────
    log.info("\n=== VALIDATION METRICS ===")
    metrics = evaluate(model, feat_df, target=TARGET_TOTAL)

    print("\n" + "=" * 60)
    print("  VALIDATION SET METRICS  (split: 2023-07-01)")
    print("=" * 60)
    print(metrics.to_string(float_format="{:.1f}".format))
    print("=" * 60)

    # ── plots ─────────────────────────────────────────────────────────────────
    plot_pred_vs_actual(model, feat_df, target=TARGET_TOTAL,
                        station_id=9033, direction="R1", n_weeks=2)
    plot_feature_importance(model)

    # ── save ──────────────────────────────────────────────────────────────────
    save_model(model, meta)

    # ── quick forecast smoke-test ─────────────────────────────────────────────
    log.info("\nSmoke-test: 1-week forecast for zst9033 R1 …")
    fc = predict(model, meta,
                 station_id=9033, direction="R1",
                 start="2024-01-01", end="2024-01-08",
                 df_history=df)
    print(fc.head(10).to_string(index=False))
    log.info("Forecast shape: %s  |  mean=%.0f Kfz/h  |  min=%.0f  |  max=%.0f",
             fc.shape, fc["forecast"].mean(), fc["forecast"].min(), fc["forecast"].max())

    log.info("Done.")


if __name__ == "__main__":
    main()
