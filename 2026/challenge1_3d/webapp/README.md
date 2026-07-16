# Opening Detect — Web App

Upload construction-plan PDFs in your browser and get back a structured
**Excel opening list** for concrete-3D-print formwork prefabrication.

## Run it
```bash
cd webapp
pip install -r requirements.txt
python start.py            # opens http://localhost:5000 automatically
#   (or)  python app.py    # then open http://localhost:5000 yourself
```

## How to use
1. Drag one or more plan PDFs onto the upload area (or click to browse).
2. Press **Detect openings → build Excel**.
3. Review the summary cards, the plan preview with detected openings, and the
   sortable opening table.
4. Click **Download Excel report**.

Uploading **several overlapping sheets at once** lets the engine match them and
remove duplicate openings automatically.

## What the engine does
- Detects `DDB` (slab / Deckendurchbruch) and `WDB` (wall / Wanddurchbruch) labels.
- Interprets both `L/W` (rectangular, cm) and `Ø` (round diameter) dimensions,
  whether the prefix and number are one token or split.
- Reads slab height from the nearest `RDOK`/`RDUK` levels.
- Removes double-drawn labels and de-duplicates overlapping sheets
  (translation registration on matching labels).
- Computes handling weight (displaced concrete × 2.4 t/m³; round = circular area).
- Builds an Excel workbook (Slab / Wall / Summary sheets, live weight formulas).

## Files
- `app.py` — Flask routes (`/`, `/process`, `/download/<job>`)
- `pipeline.py` — detection + dedup + Excel engine
- `templates/index.html` — the web UI
- `start.py` — launcher

## Notes
- Works on vector PDFs that carry embedded text (these plans do); scanned raster
  plans would need an added OCR/CV stage.
- Jobs are kept in memory; the download link is valid while the server runs.
