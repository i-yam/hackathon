# Hackathon 2026

Solutions repository for Hackathon 2026.

**➡️ Solution:** [`challenge1_3d/`](challenge1_3d) — Floor-Slab Opening Detection (Riedelbau 3D-print challenge)

## Challenges

### [`challenge1_3d/`](challenge1_3d) — Floor-Slab Opening Detection

Automatically detects floor-slab openings (for pipes, cables, and technical
installations) from construction-plan PDFs and produces structured data for
additive prefabrication of formwork via concrete 3D printing.

The pipeline detects `DDB` (slab / *Deckendurchbruch*) and `WDB` (wall /
*Wanddurchbruch*) annotations from vector PDFs, interprets rectangular (`60/45`)
and round (`Ø13`) dimensions, reads slab heights from `RDOK`/`RDUK` level pairs,
de-duplicates openings across overlapping sheets, computes handling weight, and
exports an Excel/CSV opening list plus an interactive plan viewer.

See [`challenge1_3d/README.md`](challenge1_3d/README.md) and
[`challenge1_3d/webapp/README.md`](challenge1_3d/webapp/README.md) for full
details.

## Repository layout
```
2026/
├── readme.md                  # this file
└── challenge1_3d/             # slab-opening detection challenge
    ├── README.md              # challenge details
    ├── run_pipeline.py        # one-shot CLI pipeline
    ├── extract_openings.py    # detection + label interpretation
    ├── dedup_and_export.py    # cross-plan registration + de-duplication
    ├── build_excel.py         # Excel/CSV builder
    ├── viewer/                # interactive plan viewer
    └── webapp/                # Flask upload-and-detect web app
```
