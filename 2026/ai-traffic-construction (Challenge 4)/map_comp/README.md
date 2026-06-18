# A3-Karte – Zählstellen, Abschnitte & Fahrtrichtungen

Interaktive Leaflet-Karte der BAB A3 (Deutschland) mit allen Zählstellen,
ihren Abschnitten (`Abschnitt_Ast` / Spalte HW) und beiden Richtungsfahrbahnen.

## Ordnerstruktur

```
A3_Karte_App/
├─ rohdaten/        # Eingabedaten (Rohdaten)
│  ├─ Jawe2023.csv  #   BASt-Jahresauswertung 2023: Zählstellen, Koordinaten, Abschnitt_Ast
│  └─ a3_osm.json   #   A3-Straßengeometrie aus OpenStreetMap (Overpass-Export)
├─ skript/
│  └─ build_a3_osm_map.ps1   # Verarbeitung: liest Rohdaten -> erzeugt das HTML
└─ html/
   └─ a3_karte.html # Fertige, eigenständige Karte (in die App einbinden)
```

## Nutzung / Neu generieren

```powershell
powershell -ExecutionPolicy Bypass -File .\skript\build_a3_osm_map.ps1
```

Das Skript findet die Rohdaten automatisch unter `../rohdaten` und schreibt das
Ergebnis nach `../html/a3_karte.html`. Pfade lassen sich per Parameter überschreiben
(`-Jawe`, `-Osm`, `-OutFile`).

## In die Application einbinden

`html/a3_karte.html` ist **eigenständig** – die einzige externe Abhängigkeit ist
Leaflet (CSS/JS via unpkg-CDN) und die OSM-Kartenkacheln. Möglichkeiten:

- Direkt als statische Datei ausliefern bzw. per `<iframe src="a3_karte.html">` einbetten.
- Oder den `<script>`-Block aus dem HTML in eine bestehende Leaflet-Seite übernehmen.

## Was die Karte zeigt

- **89 Zählstellen** der A3 als Punkt-Marker. Hover zeigt Knotendetails
  (Zst-Nr, Standort, Land, `Abschnitt_Ast`, Von-/Nach-Netzknoten, Betriebs-km).
- **Beide Richtungsfahrbahnen** getrennt (OSM `oneway`-Wege):
  - Blau = Richtung Süd-Ost (Passau)
  - Rot  = Richtung Nord-West (Oberhausen)
- **Abschnitte**: Helligkeitswechsel entlang der Fahrbahn (Zuordnung über die
  nächstgelegene Zählstelle).
- Basiskarte leicht ausgegraut, damit die Strecke im Vordergrund steht.

## Datenquellen

- Zählstellen/Abschnitte: BASt Jahresauswertung 2023 (Jawe2023).
- Straßengeometrie: © OpenStreetMap-Mitwirkende (ODbL), via Overpass API.
  Hinweis: Die luxemburgische `A 3` ist im OSM-Export enthalten und wird im
  Skript per Geofilter ausgeblendet.

## Daten aktualisieren

- **Neue Jahresauswertung**: `rohdaten/Jawe2023.csv` ersetzen (Spaltennamen müssen gleich bleiben).
- **OSM-Geometrie neu laden** (Overpass):

  ```
  [out:json][timeout:300];
  area["ISO3166-1"="DE"][admin_level=2]->.de;
  way(area.de)[highway=motorway][ref="A 3"];
  out geom;
  ```

  Ergebnis als `rohdaten/a3_osm.json` speichern.
