"""Zwischenmodell (Single Source of Truth) fuer den Schallschutznachweis nach DIN 4109.

Dieses Modell verbindet die beiden Stufen:
  Stufe 1 (KI-Extraktion / IFC / Excel)  -->  Gebaeudemodell  -->  Stufe 2 (DIN-Engine + Report)

Bewusst entkoppelt: die deterministische Engine (engine.py / nachweis.py) arbeitet
ausschliesslich auf diesem Modell und ist damit unabhaengig von der Herkunft der Daten.
"""
from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class Gebaeudetyp(str, Enum):
    MEHRFAMILIENHAUS = "mehrfamilienhaus"
    REIHENHAUS_DOPPELHAUS = "reihenhaus_doppelhaus"
    GEMISCHT = "gemischt"


class Bauteiltyp(str, Enum):
    WAND = "wand"
    DECKE = "decke"
    TUER = "tuer"
    FENSTER = "fenster"


class Schicht(BaseModel):
    """Eine Materialschicht eines Bauteilaufbaus (von innen nach aussen)."""
    material: str = Field(..., description="Materialname oder Alias (siehe data/materials.json)")
    dicke_mm: float = Field(..., gt=0, description="Schichtdicke in mm")
    rohdichte_override: Optional[float] = Field(
        None, description="Optionale Rohdichte kg/m3, falls vom Katalogwert abweichend (z.B. aus Planbeschriftung)"
    )


class Raum(BaseModel):
    id: str
    name: str
    nutzung: str = Field("aufenthaltsraum", description="z.B. schlafraum, wohnraum, bad, treppenraum, flur")
    nutzungseinheit: Optional[str] = Field(None, description="ID der Wohnung/Einheit, zu der der Raum gehoert")
    geschoss: Optional[str] = None
    flaeche_m2: Optional[float] = None
    laenge_m: Optional[float] = None
    breite_m: Optional[float] = None
    hoehe_m: Optional[float] = None


class Bauteil(BaseModel):
    """Ein Trennbauteil (Wand/Decke/Tuer/Fenster) zwischen zwei Raeumen/Einheiten."""
    id: str
    typ: Bauteiltyp
    din_rolle: Optional[str] = Field(
        None,
        description="DIN-4109-1 Rolle (Schluessel in data/requirements.json), "
        "z.B. wohnungstrennwand, wohnungstrenndecke, treppenraumwand. "
        "Bestimmt den Anforderungswert. Wird in der Mapping-Stufe gesetzt.",
    )
    raum_a: Optional[str] = Field(None, description="ID Raum/Seite A")
    raum_b: Optional[str] = Field(None, description="ID Raum/Seite B")
    verschiedene_einheiten: bool = Field(
        True, description="True, wenn das Bauteil fremde Nutzungseinheiten trennt (loest DIN-Anforderung aus)"
    )
    flaeche_m2: Optional[float] = None
    # Geometrie (raum-zentrische Extraktion): Wandmasse
    laenge_m: Optional[float] = Field(None, description="Wandlaenge in m")
    hoehe_m: Optional[float] = Field(None, description="Wandhoehe (i.d.R. Raumhoehe) in m")
    fenster_flaeche_m2: Optional[float] = Field(None, description="Fensterflaeche in dieser Wand (gesamt), m2")
    schichten: list[Schicht] = Field(default_factory=list)

    # Vorsatzkonstruktion (DIN 4109-34): Luftschall-Verbesserung
    delta_rw_vorsatz: float = Field(0.0, description="Bewertete Luftschallverbesserung dRw durch Vorsatzschale, dB (DIN 4109-34)")

    # Trittschall (nur bei Decken relevant): Verbesserung durch Estrich/Belag
    delta_lw: float = Field(0.0, description="Trittschallverbesserung dLw durch schwimmenden Estrich / Bodenbelag, dB (DIN 4109-34)")

    # direkter Tuer-/Fensterwert (falls kein Massivaufbau): bewertetes Schalldaemm-Mass des Elements
    rw_element: Optional[float] = Field(None, description="Direkt vorgegebenes Rw (z.B. Tuer/Fenster aus Datenblatt), dB")

    # Lage auf dem Plan (relativ 0..1: [x0, y0, x1, y1]) fuer die Overlay-Visualisierung
    bbox: Optional[list[float]] = Field(None, description="Relative Bounding-Box [x0,y0,x1,y1] auf dem Planbild")

    bemerkung: Optional[str] = None


class Nutzungseinheit(BaseModel):
    id: str
    name: str
    raeume: list[str] = Field(default_factory=list)


class Gebaeude(BaseModel):
    typ: Gebaeudetyp = Gebaeudetyp.MEHRFAMILIENHAUS
    geschosse: Optional[int] = None
    erhoehter_schallschutz: bool = Field(False, description="DIN 4109-5 (erhoehte Anforderungen) anwenden")


class Projekt(BaseModel):
    """Wurzel des Zwischenmodells."""
    name: str = "Schallschutznachweis"
    bauvorhaben: Optional[str] = None
    bearbeiter: Optional[str] = None
    quelle_plan: Optional[str] = Field(None, description="Dateiname/Pfad des extrahierten Plans")
    gebaeude: Gebaeude = Field(default_factory=Gebaeude)
    nutzungseinheiten: list[Nutzungseinheit] = Field(default_factory=list)
    raeume: list[Raum] = Field(default_factory=list)
    bauteile: list[Bauteil] = Field(default_factory=list)
