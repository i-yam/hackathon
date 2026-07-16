# Floor-Slab Opening Detection — Prototype (Floor U1)

Automatically detects floor-slab openings (for pipes, cables and technical
installations) from construction plans and produces structured data for
additive prefabrication of formwork with concrete 3D printing.

## What it does
1. **Detect** opening annotations in the vector PDFs (no OCR needed — the plans
   carry embedded text).
   - `DDB` = *Deckendurchbruch* → **slab opening** (the 3D-print fabrication target)
   - `WDB` = *Wanddurchbruch* → wall opening (detected separately, different trade)
2. **Interpret varying labels**: handles `60/45` (rectangular L×W cm) and `Ø13`
   (round, diameter), whether the prefix and dimension are one token or split.
3. **Extract** geometry, dimensions, position, and **slab height** (from the
   nearest `RDOK`/`RDUK` slab-level pair).
4. **Match overlapping plans**: registers plan pairs by a common translation
   offset (RANSAC-style on matching labels) and **removes duplicates** that
   appear in more than one sheet, plus double-drawn labels within a sheet.
5. **Calculate weight** for safe handling (displaced concrete volume × 2.4 t/m³;
   round openings use the circular area).
6. **Output** a structured Excel/CSV list + an interactive plan viewer.

## Run it
```
pip install pymupdf openpyxl
python3 run_pipeline.py
```

## Outputs
- `U1_Opening_Report.xlsx` — Slab list, Wall list, All-detections audit, Summary
  (the Weight column is a live Excel formula).
- `U1_Slab_Openings.csv` — slab openings, machine-readable for the printer pipeline.
- `viewer/Slab_Opening_Viewer.html` — open in a browser; pan/zoom, filter by
  type, toggle duplicates, click any opening for its fabrication data.

## Pipeline files
- `extract_openings.py` — detection + interpretation engine
- `dedup_and_export.py` — overlap registration + de-duplication
- `build_excel.py` — workbook/CSV builder

## Known limitations (prototype)
- Geometry round/rect comes from the `Ø` marker / `a/b` form; symbols without a
  text label are not detected (a CV fallback would cover scanned plans).
- Slab height uses the nearest level pair; a few openings in dense areas may need
  manual review.
- Cross-plan registration is deliberately conservative (≥3 corroborating matches)
  to avoid false merges.
