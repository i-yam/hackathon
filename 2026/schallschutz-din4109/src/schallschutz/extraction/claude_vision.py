"""Stufe 1: Extraktion eines Gebaeudemodells aus Plan-PDF/Bild via Claude Vision (Agent SDK + Max-Abo).

Workflow: PDF -> PNG (pymupdf) -> Claude liest Bild per Read-Tool -> JSON -> Projekt-Modell.
Kein API-Key noetig; Auth ueber lokale Claude-Code-Session.
"""
from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path

from ..models import Projekt
from .schema import build_extraction_prompt

_IMG_SUFFIXES = {".png", ".jpg", ".jpeg", ".bmp", ".webp"}


def pdf_to_images(pdf_path: str | Path, out_dir: str | Path, dpi: int = 200) -> list[Path]:
    """Rendert jede PDF-Seite als PNG (hohe DPI fuer lesbare Schraffuren/Beschriftungen)."""
    import fitz

    pdf_path = Path(pdf_path)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    doc = fitz.open(pdf_path)
    paths: list[Path] = []
    zoom = dpi / 72.0
    mat = fitz.Matrix(zoom, zoom)
    for i, page in enumerate(doc):
        pix = page.get_pixmap(matrix=mat)
        p = out_dir / f"{pdf_path.stem}_seite{i + 1}.png"
        pix.save(p)
        paths.append(p)
    return paths


def plan_to_images(plan_path: str | Path, out_dir: str | Path, dpi: int = 200) -> list[Path]:
    """Akzeptiert PDF oder Bild und liefert eine Liste von Bildpfaden."""
    plan_path = Path(plan_path)
    if plan_path.suffix.lower() == ".pdf":
        return pdf_to_images(plan_path, out_dir, dpi)
    if plan_path.suffix.lower() in _IMG_SUFFIXES:
        return [plan_path]
    raise ValueError(f"Nicht unterstuetztes Format: {plan_path.suffix}")


def _extract_json(text: str) -> dict:
    """Holt das JSON-Objekt aus Claudes Antwort (Codeblock bevorzugt, sonst erstes {...})."""
    m = re.search(r"```json\s*(\{.*?\})\s*```", text, re.DOTALL)
    if not m:
        m = re.search(r"```\s*(\{.*?\})\s*```", text, re.DOTALL)
    raw = m.group(1) if m else None
    if raw is None:
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end == -1:
            raise ValueError("Keine JSON-Struktur in der Antwort gefunden.")
        raw = text[start:end + 1]
    return json.loads(raw)


async def _query_claude(prompt: str) -> str:
    from claude_agent_sdk import ClaudeAgentOptions, query

    opts = ClaudeAgentOptions(allowed_tools=["Read"], permission_mode="bypassPermissions")
    chunks: list[str] = []
    async for msg in query(prompt=prompt, options=opts):
        for block in getattr(msg, "content", []) or []:
            txt = getattr(block, "text", None)
            if txt:
                chunks.append(txt)
    return "\n".join(chunks)


def extrahiere_modell(plan_path: str | Path, arbeitsordner: str | Path = "outputs/_plan_pages",
                      dpi: int = 200) -> tuple[Projekt, dict, list[Path]]:
    """Hauptfunktion: Plan -> (validiertes Projekt, rohes JSON, Bildpfade).

    Wirft bei Validierungsfehlern eine Exception; das rohe JSON bleibt fuer Debugging im Rueckgabewert.
    """
    images = plan_to_images(plan_path, arbeitsordner, dpi)
    prompt = build_extraction_prompt([str(p.resolve()) for p in images], Path(plan_path).name)
    antwort = asyncio.run(_query_claude(prompt))
    roh = _extract_json(antwort)
    roh.setdefault("quelle_plan", Path(plan_path).name)
    projekt = Projekt.model_validate(roh)
    return projekt, roh, images
