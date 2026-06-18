"""
clean_data.py — A3 BASt traffic counter cleaning pipeline
==========================================================
Input:   data/{year}/.../*.csv  and  data/{year}/zst*.zip
Output:  data_clean/  (Parquet partitioned by year / station_id)

Schema produced
---------------
timestamp            datetime64[ns]   start of the hourly interval (local time)
station_id           Int32            BASt Zählstellen-ID  (e.g. 9010)
station_name         str              "A3-zst{id}"  (no official name in source)
direction            category         "R1" or "R2"
km_marker            float64          NaN — not present in source files
vehicle_count_total  Int32            KFZ (all motorised vehicles); NaN = gap
vehicle_count_heavy  Int32            Lkw (≥3.5 t HGV);            NaN = gap
quality_flag         category         '-' valid | 's' estimated | 'u' implausible
day_type             category         BASt Fahrtzweck: 'w' | 'u' | 's' (NaN=gap)
year                 Int16
month                Int8
week                 Int8             ISO week number
dayofweek            Int8             0=Monday … 6=Sunday
hour                 Int8             0-23
is_weekend           bool
is_holiday           bool             Bayern (BY) public holidays
season               category         winter | spring | summer | autumn

Dependencies:  pandas>=1.3  pyarrow>=6  holidays>=0.14
"""

import io
import logging
import os
import sys
import warnings
import zipfile
from pathlib import Path

# Force UTF-8 output on Windows consoles so box-drawing / arrows don't crash
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf_8"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if sys.stderr.encoding and sys.stderr.encoding.lower() not in ("utf-8", "utf_8"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import holidays as hol_lib
import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", message="For backward compatibility")

# ── configuration ─────────────────────────────────────────────────────────────
DATA_DIR   = Path("data")
OUT_DIR    = Path("data_clean")
ENCODING   = "latin-1"
SEP        = ";"
YEARS      = ["2018", "2022", "2023"]
BUNDESLAND = "BY"          # Bayern / Bavaria

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# ── season lookup ─────────────────────────────────────────────────────────────
_SEASON = {
    12: "winter", 1: "winter", 2: "winter",
    3: "spring",  4: "spring",  5: "spring",
    6: "summer",  7: "summer",  8: "summer",
    9: "autumn", 10: "autumn", 11: "autumn",
}


# ════════════════════════════════════════════════════════════════════════════════
# I/O
# ════════════════════════════════════════════════════════════════════════════════

def iter_files():
    """Yield (year_str, zst_str, kind, Path) for every station-year file."""
    for year in YEARS:
        year_dir = DATA_DIR / year
        for fp in sorted(year_dir.glob("**/*.csv")):
            yield year, fp.stem.split("_")[0].lower(), "csv", fp
        for fp in sorted(year_dir.glob("*.zip")):
            yield year, fp.stem.lower(), "zip", fp


def _read_csv_bytes(raw_bytes: bytes) -> pd.DataFrame:
    text = raw_bytes.decode(ENCODING)
    return pd.read_csv(io.StringIO(text), sep=SEP, skipinitialspace=True)


def read_raw(kind: str, path: Path) -> pd.DataFrame:
    if kind == "csv":
        return pd.read_csv(path, sep=SEP, encoding=ENCODING, skipinitialspace=True)
    with zipfile.ZipFile(path) as zf:
        name = zf.namelist()[0]
        with zf.open(name) as f:
            return _read_csv_bytes(f.read())


# ════════════════════════════════════════════════════════════════════════════════
# Parsing helpers
# ════════════════════════════════════════════════════════════════════════════════

def parse_timestamp(df: pd.DataFrame) -> pd.Series:
    """
    Datum (YYMMDD integer, e.g. 180101) + Stunde (1-24)
    → timestamp at the *start* of the hourly interval.

    BASt convention: Stunde=1  covers 00:00–01:00  → stored as 00:00
                     Stunde=24 covers 23:00–24:00  → stored as 23:00
    """
    datum_str = df["Datum"].astype(str).str.zfill(6)
    base = pd.to_datetime(datum_str, format="%y%m%d", errors="raise")
    return base + pd.to_timedelta(df["Stunde"].astype(int) - 1, unit="h")


def melt_directions(df: pd.DataFrame) -> pd.DataFrame:
    """
    Split each raw row (one per hour per station) into two rows —
    one for direction R1, one for R2.

    Keeps: timestamp, station_id, station_name, km_marker, day_type,
           vehicle_count_total, vehicle_count_heavy, quality_flag.
    """
    shared = ["timestamp", "station_id", "station_name", "km_marker", "day_type"]

    r1 = df[shared].copy()
    r1["direction"]           = "R1"
    r1["vehicle_count_total"] = df["KFZ_R1"].astype("Int32")
    r1["vehicle_count_heavy"] = df["Lkw_R1"].astype("Int32")
    r1["quality_flag"]        = df["K_KFZ_R1"].str.strip()

    r2 = df[shared].copy()
    r2["direction"]           = "R2"
    r2["vehicle_count_total"] = df["KFZ_R2"].astype("Int32")
    r2["vehicle_count_heavy"] = df["Lkw_R2"].astype("Int32")
    r2["quality_flag"]        = df["K_KFZ_R2"].str.strip()

    return pd.concat([r1, r2], ignore_index=True)


# ════════════════════════════════════════════════════════════════════════════════
# Resampling — complete hourly index
# ════════════════════════════════════════════════════════════════════════════════

def make_complete_index(df: pd.DataFrame) -> pd.DataFrame:
    """
    For every (station_id, direction, year) group, reindex onto the full
    365-day hourly grid.  Slots absent in the raw data become NaN rows.
    Grouping per calendar year avoids inserting phantom NaN rows for years
    that simply have no data for a given station.
    """
    groups = []
    grp_cols = ["station_id", "direction", "_yr"]

    for (sid, direction, yr), grp in df.groupby(grp_cols, sort=False, observed=True):
        year_int  = int(yr)
        full_idx  = pd.date_range(
            start=f"{year_int}-01-01 00:00",
            end=f"{year_int}-12-31 23:00",
            freq="h",
        )
        n_gaps = len(full_idx) - len(grp)
        if n_gaps:
            log.warning(
                "  Gap detected: station %s direction %s year %s — "
                "%d/%d hours present (%d missing)",
                sid, direction, year_int, len(grp), len(full_idx), n_gaps,
            )

        reindexed = grp.set_index("timestamp").reindex(full_idx)
        reindexed.index.name = "timestamp"

        # Restore keys that were NaN'd during reindex
        reindexed["station_id"]   = sid
        reindexed["direction"]    = direction
        reindexed["station_name"] = f"A3-zst{sid}"
        reindexed["km_marker"]    = np.nan   # not in source data

        groups.append(reindexed.reset_index())

    return pd.concat(groups, ignore_index=True)


# ════════════════════════════════════════════════════════════════════════════════
# Feature engineering
# ════════════════════════════════════════════════════════════════════════════════

def add_time_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Derives calendar and holiday features from the timestamp column.
    Works correctly on both real and gap-fill rows (timestamp is always valid).
    """
    ts = df["timestamp"]

    # Build Bavaria holiday set for all years present in the data
    years_present = {int(y) for y in ts.dt.year.dropna().unique()}
    bavaria_hols  = set(
        hol_lib.Germany(state=BUNDESLAND, years=years_present).keys()
    )

    df["year"]       = ts.dt.year.astype("Int16")
    df["month"]      = ts.dt.month.astype("Int8")
    df["week"]       = ts.dt.isocalendar().week.astype("Int8")
    df["dayofweek"]  = ts.dt.dayofweek.astype("Int8")   # 0=Mon … 6=Sun
    df["hour"]       = ts.dt.hour.astype("Int8")
    df["is_weekend"] = ts.dt.dayofweek.isin([5, 6])
    df["is_holiday"] = ts.dt.date.isin(bavaria_hols)
    df["season"]     = ts.dt.month.map(_SEASON).astype("category")

    return df


# ════════════════════════════════════════════════════════════════════════════════
# Output
# ════════════════════════════════════════════════════════════════════════════════

# Column order in the output Parquet
_OUTPUT_COLS = [
    "timestamp",
    "station_id", "station_name", "direction", "km_marker",
    "vehicle_count_total", "vehicle_count_heavy",
    "quality_flag", "day_type",
    "year", "month", "week", "dayofweek", "hour",
    "is_weekend", "is_holiday", "season",
]


def save_parquet(df: pd.DataFrame, out_dir: Path) -> None:
    """Write partitioned Parquet dataset (partition by year / station_id)."""
    out_dir.mkdir(parents=True, exist_ok=True)

    # year must be plain int for pyarrow partition encoding
    save_df = df.copy()
    save_df["year"]       = save_df["year"].astype(int)
    save_df["station_id"] = save_df["station_id"].astype(int)

    table = pa.Table.from_pandas(
        save_df[_OUTPUT_COLS],
        preserve_index=False,
    )
    pq.write_to_dataset(
        table,
        root_path=str(out_dir),
        partition_cols=["year", "station_id"],
    )
    log.info("Parquet written → %s", out_dir)


# ════════════════════════════════════════════════════════════════════════════════
# Validation report
# ════════════════════════════════════════════════════════════════════════════════

def print_validation(raw_rows: int, df: pd.DataFrame) -> None:
    gap_rows   = df["vehicle_count_total"].isna().sum()
    real_rows  = len(df) - gap_rows

    flag_counts = df["quality_flag"].value_counts(dropna=False)
    n_estimated  = flag_counts.get("s", 0)
    n_implausible= flag_counts.get("u", 0)
    n_valid      = flag_counts.get("-", 0)
    n_flag_nan   = int(df["quality_flag"].isna().sum())

    sanity_fail = int(
        (df["vehicle_count_total"].notna() & df["vehicle_count_heavy"].notna() &
         (df["vehicle_count_total"] < df["vehicle_count_heavy"])).sum()
    )

    neg_total = int(
        (df["vehicle_count_total"].notna() & (df["vehicle_count_total"] < 0)).sum()
    )

    print()
    print("=" * 65)
    print("  VALIDATION SUMMARY")
    print("=" * 65)
    print(f"  Raw rows loaded (pre-melt, one direction-pair per hour): {raw_rows:>10,}")
    print(f"  After melt (×2 directions):                              {raw_rows*2:>10,}")
    print(f"  After complete-index reindex:                            {len(df):>10,}")
    print(f"    +- real data rows                                       {real_rows:>10,}")
    print(f"    +- inserted gap-fill NaN rows                           {gap_rows:>10,}")
    print()
    print("  Quality flag breakdown (vehicle_count_total direction R1 & R2):")
    print(f"    '-'  valid / directly measured                          {n_valid:>10,}")
    print(f"    's'  estimated / imputed by BASt                        {n_estimated:>10,}")
    print(f"    'u'  implausible (treat as missing)                     {n_implausible:>10,}")
    print(f"    NaN  gap-fill rows (no source record)                   {n_flag_nan:>10,}")
    print()
    print("  Sanity checks:")
    print(f"    KFZ_total < Lkw_heavy (impossible):                     {sanity_fail:>10,}")
    print(f"    Negative vehicle counts:                                 {neg_total:>10,}")
    print()
    print(f"  Timestamp range : {df['timestamp'].min()}  ->  {df['timestamp'].max()}")
    print(f"  Unique stations : {df['station_id'].nunique()}")
    yr_sid = df.groupby(["year", "station_id"], observed=True).ngroups
    print(f"  Station-years   : {yr_sid}")
    print(f"  (station, direction) pairs: {df.groupby(['station_id','direction'], observed=True).ngroups}")
    print()
    print("  Holiday coverage (Bavaria / BY):")
    hol_hours = df[df["is_holiday"]]["vehicle_count_total"].count()
    print(f"    Rows on public holidays (with data): {hol_hours:>10,}")
    print()
    print("  Season distribution:")
    season_counts = df.groupby("season", observed=True)["vehicle_count_total"].count()
    for s, n in season_counts.items():
        print(f"    {s:<8}: {n:>10,} data rows")
    print("=" * 65)
    print()


# ════════════════════════════════════════════════════════════════════════════════
# Main
# ════════════════════════════════════════════════════════════════════════════════

def main() -> None:
    all_frames: list[pd.DataFrame] = []
    raw_total = 0

    log.info("Scanning %s …", DATA_DIR)
    file_list = list(iter_files())
    log.info("Found %d station-year files", len(file_list))

    for year, zst, kind, path in file_list:
        log.info("  loading  %s / %s  (%s)", year, zst, kind)
        raw = read_raw(kind, path)
        raw.columns = raw.columns.str.strip()

        # Normalise all object columns (strip whitespace)
        for col in raw.select_dtypes(include="object").columns:
            raw[col] = raw[col].str.strip()

        station_id = int(raw["Zst"].iloc[0])

        raw["timestamp"]    = parse_timestamp(raw)
        raw["station_id"]   = station_id
        raw["station_name"] = f"A3-zst{station_id}"
        raw["km_marker"]    = np.nan   # not present in source files
        raw["day_type"]     = raw["Fahrtzw"]

        raw_total += len(raw)
        all_frames.append(melt_directions(raw))

    # ── concatenate ───────────────────────────────────────────────────────────
    log.info("Concatenating %d frames …", len(all_frames))
    df = pd.concat(all_frames, ignore_index=True)

    # ── complete hourly index ─────────────────────────────────────────────────
    log.info("Building complete hourly index per (station, direction, year) …")
    df["_yr"] = df["timestamp"].dt.year   # groupby key; dropped after reindex
    df = make_complete_index(df)
    df = df.drop(columns="_yr", errors="ignore")

    # ── time features ─────────────────────────────────────────────────────────
    log.info("Adding time features …")
    df = add_time_features(df)

    # ── final dtypes ──────────────────────────────────────────────────────────
    df["station_id"]   = df["station_id"].astype("Int32")
    df["direction"]    = df["direction"].astype("category")
    df["quality_flag"] = df["quality_flag"].astype("category")
    df["season"]       = df["season"].astype("category")
    df["day_type"]     = df["day_type"].astype("category")
    df["station_name"] = df["station_name"].astype(str)

    # Sort for deterministic parquet row-groups
    df = df.sort_values(["station_id", "direction", "timestamp"]).reset_index(drop=True)

    # ── validation ────────────────────────────────────────────────────────────
    print_validation(raw_total, df)

    # ── save ──────────────────────────────────────────────────────────────────
    log.info("Saving partitioned Parquet → %s …", OUT_DIR)
    save_parquet(df, OUT_DIR)

    # Quick reload smoke-test
    log.info("Smoke-test: reading back one partition …")
    test = pd.read_parquet(OUT_DIR / "year=2018" / "station_id=9010")
    log.info(
        "  Read back %d rows, cols: %s",
        len(test), list(test.columns),
    )

    log.info("Pipeline complete.")


if __name__ == "__main__":
    main()
