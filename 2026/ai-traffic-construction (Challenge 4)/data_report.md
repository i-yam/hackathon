# Data Report — A3 Autobahn Traffic Counter Data (BASt / Zähldaten)

**Generated:** 2026-06-18  
**Years covered:** 2018, 2022, 2023  
**Road:** A3 (Strnum = 3), Land = 09 (Bavaria)

---

## 1. File Inventory

| Year | Format | Location | Count |
|------|--------|----------|-------|
| 2018 | CSV (in per-station subdirs) + ZIP | `data/2018/zst<id>/` or `data/2018/zst<id>.zip` | 28 files |
| 2022 | CSV (flat) | `data/2022/` | 16 files |
| 2023 | CSV (flat) | `data/2023/` | 19 files |
| **Total** | | | **63 station-year files** |

- Every ZIP contains exactly one CSV with identical formatting.  
- File naming convention: `zst<id>_<year>.csv`

### Encoding & delimiters

| Property | Value |
|----------|-------|
| Encoding | Latin-1 (ISO 8859-1) |
| Delimiter | `;` (semicolon) |
| Decimal separator | none — all traffic values are **integers** |
| Header | Yes, row 1 |

---

## 2. Schema

57 columns per file. All columns are consistent across all years and stations.

### Metadata / identifier columns

| Column | Dtype | Description |
|--------|-------|-------------|
| `TKNR` | int64 | Telezählknoten-Nummer (counting-node ID) |
| `Zst` | int64 | Zählstelle (counting station ID, e.g. 9010) |
| `Land` | int64 | Federal state code — all rows = 9 (Bavaria) |
| `Strklas` | str | Road class — all rows = `A` (Autobahn) |
| `Strnum` | int64 | Road number — all rows = 3 (A3) |
| `Datum` | int64 | Date as **YYMMDD integer**, e.g. 180101 = 2018-01-01 |
| `Wotag` | int64 | Day of week: 1 = Monday … 7 = Sunday |
| `Fahrtzw` | str | Day-type classification: `w` (weekday), `u` (holiday/vacation), `s` (weekend/Sunday-profile) |
| `Stunde` | int64 | Hour of day: 1 – 24 |

> **Date parsing note:** `Datum` must be parsed with `pd.to_datetime(..., format="%y%m%d")` after zero-padding to 6 digits.

### Traffic count columns (per direction)

Traffic is measured in **two directions** (`_R1` = direction 1, `_R2` = direction 2).

| Column(s) | Description |
|-----------|-------------|
| `KFZ_R1`, `KFZ_R2` | Total vehicles (Kraftfahrzeuge) — primary volume metric |
| `Lkw_R1`, `Lkw_R2` | Heavy goods vehicles (Lastkraftwagen ≥ 3.5 t) |
| `PLZ_R1`, `PLZ_R2` | Light-vehicle aggregate (PKW-ähnliche Fahrzeuge; ≈ KFZ − Lkw) |
| `Pkw_R1`, `Pkw_R2` | Passenger cars (Personenkraftwagen) |
| `Lfw_R1`, `Lfw_R2` | Light vans (Lieferwagen) |
| `Mot_R1`, `Mot_R2` | Motorcycles (Motorräder) |
| `PmA_R1`, `PmA_R2` | Passenger cars with trailer (PKW mit Anhänger) |
| `Bus_R1`, `Bus_R2` | Buses |
| `LoA_R1`, `LoA_R2` | Lorries without trailer (Lkw ohne Anhänger) |
| `Lzg_R1`, `Lzg_R2` | Road trains (Lastzüge) |
| `Sat_R1`, `Sat_R2` | Semi-trailers (Sattelzüge) |
| `Son_R1`, `Son_R2` | Other / special vehicles (Sonstige) |

**Vehicle class hierarchy:**  
`KFZ = PLZ + Lkw`  (approximately; minor rounding differences exist)  
`Lkw ≈ LoA + Lzg + Sat + Son`  
`PLZ ≈ Pkw + Lfw + Mot` (main components)

### Quality flag columns (`K_` prefix)

Each traffic column has a paired `K_<col>` quality flag:

| Flag | Meaning |
|------|---------|
| `-` | Valid, no issues |
| `s` | Estimated / imputed (German: *Schätzwert*) |
| `u` | Implausible value (German: *unplausibel*) — rare |
| `z` | Special marker — appears exactly twice per station-year (likely period boundary) |

---

## 3. Sample Rows (zst9010, 2018-01-01, hours 1–5)

```
Datum   Wotag  Fahrtzw  Stunde  KFZ_R1  KFZ_R2  Lkw_R1  Lkw_R2  PLZ_R1  PLZ_R2
180101      1        w       1      89      84       5       6      84      78
180101      1        w       2     182     187      14       5     168     182
180101      1        w       3     171     229       7       8     163     221
180101      1        w       4     135     193       7       5     126     187
180101      1        w       5     104     134       9       4      92     130
```

---

## 4. Temporal Granularity & Date Range

| Property | Value |
|----------|-------|
| Granularity | **Hourly** (one row per station per hour) |
| Hours encoding | 1 – 24 (hour 1 = midnight–1 am) |
| 2018 range | 2018-01-01 – 2018-12-31 |
| 2022 range | 2022-01-01 – 2022-12-31 |
| 2023 range | 2023-01-01 – 2023-12-31 |
| Rows per station-year | **8 760** (365 days × 24 h) |
| Total rows across all files | **551 880** |

No 15-minute or sub-hourly data is present.

---

## 5. Counting Stations

**32 unique stations** along the A3 in Bavaria.

### Coverage by year

| Station | 2018 | 2022 | 2023 |
|---------|:----:|:----:|:----:|
| zst9010 | Y | Y | Y |
| zst9011 | Y | Y | Y |
| zst9027 | Y | Y | — |
| zst9033 | Y | Y | Y |
| zst9034 | Y | Y | Y |
| zst9036 | Y | Y | Y |
| zst9040 | Y | Y | Y |
| zst9041 | Y | — | — |
| zst9046 | Y | — | — |
| zst9050 | Y | — | Y |
| zst9051 | Y | — | Y |
| zst9074 | Y | Y | Y |
| zst9081 | Y | Y | Y |
| zst9085 | — | Y | Y |
| zst9093 | — | Y | Y |
| zst9159 | Y | Y | Y |
| zst9251 | Y | — | — |
| zst9252 | Y | Y | — |
| zst9507 | Y | Y | Y |
| zst9508 | Y | Y | Y |
| zst9509 | — | — | Y |
| zst9511 | Y | — | — |
| zst9512 | Y | — | — |
| zst9515 | Y | — | — |
| zst9516 | Y | — | — |
| zst9517 | Y | — | — |
| zst9518 | Y | — | — |
| zst9519 | Y | — | Y |
| zst9520 | — | — | Y |
| zst9521 | Y | Y | Y |
| zst9727 | Y | — | — |
| zst9951 | Y | — | — |

**Summary:**
- All-3-year stations (12): zst9010, 9011, 9033, 9034, 9036, 9040, 9074, 9081, 9159, 9507, 9508, 9521
- Only in 2018 (11): zst9041, 9046, 9251, 9511, 9512, 9515, 9516, 9517, 9518, 9727, 9951 (likely decommissioned or data not released for later years)
- Only in 2023 (2): zst9509, zst9520 (new installations)
- Missing 2022 only: no station is exclusively in 2022

---

## 6. Data Quality

### Completeness

| Metric | Result |
|--------|--------|
| Missing values in KFZ / Lkw columns | **0 across all files** |
| Duplicate (Datum × Stunde × Zst × Fahrtzw) rows | **0 across all files** |
| Files with < 8 760 rows | **0** — every station-year is exactly complete |
| Time-series gaps | **None detected** — all 365 × 24 = 8 760 hourly slots present |

### Quality flags (per station-year, `K_KFZ_R1` column)

High flag rates indicate hours where counts were estimated or imputed rather than directly measured.

| Station | 2018 flag% | 2022 flag% | 2023 flag% |
|---------|:----------:|:----------:|:----------:|
| zst9010 | 38.1% | 1.3% | 0.6% |
| zst9011 | 0.5% | 52.4% | 26.1% |
| zst9027 | 24.7% | 61.2% | — |
| zst9033 | 14.7% | 3.4% | 45.3% |
| zst9034 | 0.4% | 63.0% | 0.4% |
| zst9036 | 0.8% | 52.6% | 0.5% |
| zst9040 | 1.2% | 37.3% | 1.2% |
| zst9074 | 1.3% | 2.3% | 1.1% |
| zst9081 | 5.5% | 0.8% | 3.0% |
| zst9085 | — | 62.6% | 41.3% |
| zst9093 | — | 0.9% | 0.6% |
| zst9159 | 2.8% | 62.7% | 0.3% |
| zst9252 | 1.7% | 39.8% | — |
| zst9507 | 41.6% | 52.3% | 15.2% |
| zst9508 | 1.3% | 29.2% | 0.2% |
| zst9519 | 52.8% | — | 0.9% |
| zst9521 | 38.7% | 15.5% | 16.6% |
| zst9509 | — | — | 27.9% |
| zst9520 | — | — | 34.9% |
| zst9050 | 3.6% | — | 21.2%* |
| zst9051 | 7.5% | — | 10.6% |

> \* zst9050/2023 also contains **743 hours** with flag `u` (implausible) — the **only instance** of the `u` flag across the entire dataset. These hours should be treated with caution.

**Notable reliability concerns:**
- Stations with >40% estimated hours in any year: zst9010/2018, zst9507/2018, zst9519/2018, zst9521/2018; zst9011/2022, zst9027/2022, zst9034/2022, zst9036/2022, zst9085/2022, zst9159/2022; zst9033/2023, zst9085/2023
- 2022 has the highest overall imputation rates — many stations exceed 50% estimated hours
- Flag `z` appears exactly **2 rows per station-year** in every file (consistent sentinel, not a data problem)

---

## 7. Indicative Traffic Volumes (2018, R1 direction)

Daily average total vehicles (sum of 24 hourly counts):

| Station | Daily avg KFZ_R1 | Daily avg KFZ_R2 | Daily avg (both dirs) |
|---------|----------------:|----------------:|---------------------:|
| zst9033 | 48 012 | 52 491 | 100 503 |
| zst9519 | 49 398 | 50 713 | 100 111 |
| zst9011 | 44 950 | 41 779 | 86 729 |
| zst9010 | 37 737 | 37 819 | 75 556 |
| zst9036 | 36 886 | 36 742 | 73 628 |
| zst9034 | 33 697 | 33 130 | 66 827 |
| zst9027 | 31 972 | 33 125 | 65 097 |
| zst9040 | 23 375 | 23 001 | 46 376 |

Heavy goods vehicle (Lkw) share ranges approximately **5–15%** of total KFZ across stations.

---

## 8. Key Modelling Considerations

1. **Use `KFZ_R1` + `KFZ_R2`** as the primary volume targets; `Lkw_R1`/`Lkw_R2` for HGV-specific analysis.
2. **Filter or weight by quality flag** (`K_KFZ_R1 == '-'` for clean hours only), especially for 2022 data where many stations exceed 50% estimated.
3. **12 stations with full 3-year coverage** form the reliable longitudinal panel; the others are suitable only for cross-sectional or single-year work.
4. **No missing timestamps** — the time series is complete; no imputation of gaps needed before modelling.
5. **Fahrtzw** provides a ready-made day-type feature (w / u / s) for capturing weekend and holiday traffic profiles.
6. **Datum** must be converted from the YYMMDD integer format before any date-based feature engineering.
7. The `u`-flagged hours in zst9050/2023 (743 hours, ~8.5% of that station-year) should likely be excluded or treated as missing.
