# UI-Dokumentation · A3 Bau-Fenster-Planer

Dieses Dokument beschreibt die Oberfläche des Dashboards und erklärt wie die einzelnen Komponenten zusammenwirken.

---

## Aufbau

```
┌─────────────────────────────────────────────────┐
│  Header (Logo + Titel)                          │
├──────────────┬──────────────┬───────────────────┤
│  01 Abschnitt│  02 Dauer    │  03 Optimierungs- │
│              │              │     Ziel           │
├──────────────┴──────────────┴───────────────────┤
│  Ergebnis-Banner            │  Kennzahlen        │
├─────────────────────────────┼───────────────────┤
│  Geo-Karte (A3)             │  Top-N Fenster     │
│                             ├───────────────────┤
│                             │  Jahres-Heatmap    │
└─────────────────────────────┴───────────────────┘
│  Footer                                         │
```

---

## Eingaben (Zone 01–03)

### 01 · Streckenabschnitt
Dropdown mit 5 Abschnitten der A3 Bayern von Seligenstadt bis Passau. Jeder Abschnitt entspricht einer Gruppe von BASt-Zählstellen, deren Verkehrsdaten für die Prognose verwendet werden. Alternativ ist der Abschnitt per Klick in der Geo-Karte wählbar.

### 02 · Voraussichtliche Dauer
Voreingestellte Schaltflächen: 1 Tag · 3 Tage · 1 Woche · 2 Wochen · 4 Wochen · 8 Wochen. Die Angabe in Stunden wird an das Backend übergeben. Das Modell sucht dann zusammenhängende Zeitfenster genau dieser Länge mit dem besten Eignungs-Score.

### 03 · Optimierungs-Ziel
Drei Gewichtungsprofile:

| Modus | Priorität |
|-------|-----------|
| Geringster Verkehrseinfluss | Minimiert betroffene Kfz gesamt |
| Min. Stau-/Unfallrisiko | Gewichtet Stau-Stunden stärker |
| Schont Güter-/Pendlerverkehr | Gewichtet Lkw-Anteil und Pendlerspitzen stärker |

Jede Änderung in Zone 01–03 löst automatisch einen neuen API-Aufruf aus.

---

## Ergebnis-Banner

Zeigt das aktuell ausgewählte Zeitfenster:
- **Tag + Kalenderwochen** (z. B. „KW 26/26 – KW 28/26")
- **Datumsbereich** im Format TT.MM.JJ – TT.MM.JJ
- **Eignungs-Score** (0–100, höher = besser)
- **Aktiver Filter** und **Streckenabschnitt**

Zustände:
- **Ladebalken** oben im Fenster während API-Anfragen
- **Fehler-Banner** (rot) bei Backend-Fehler, mit „Nochmal versuchen"-Button
- **Leer-Banner** wenn für die gewählte Kombination keine Fenster gefunden wurden

---

## Kennzahlen

Vier Kacheln, die sich mit dem gewählten Zeitfenster aktualisieren:

| Kachel | Beschreibung |
|--------|-------------|
| Ø Verkehr Kfz/h | Mittlerer stündlicher Fahrzeugdurchsatz im Fenster |
| Ø Schwerlast Nfz/h | Davon abgeleiteter Lkw-Anteil pro Stunde |
| Lkw-Anteil | Prozentualer Schwerverkehrsanteil |

---

## Geo-Karte

Leaflet-Karte mit dem A3-Streckenverlauf von Seligenstadt bis Passau. Der aktive Abschnitt wird farblich hervorgehoben. Klick auf einen Abschnitt setzt den Selektor unter „01 Streckenabschnitt". Über den ⛶-Button oben rechts ist Vollbild möglich.

---

## Top-N Bau-Fenster

Liste der besten Zeitfenster, sortiert nach Eignungs-Score. Anzahl über Schaltflächen **3 / 5 / 10** einstellbar — bei 5 oder 10 werden auch suboptimale Alternativen mit niedrigerem Score angezeigt. Die Liste scrollt intern bei vielen Einträgen.

**Score-Farbgebung:**
- Grün ≥ 68 — geringer Verkehrseinfluss
- Orange 46–67 — mittlerer Kompromiss
- Rot < 46 — hoher Verkehrseinfluss

Klick auf ein Fenster → Ergebnis-Banner und Kennzahlen aktualisieren sich, ausgewähltes Fenster wird in der Heatmap markiert.

---

## Jahres-Heatmap

52 Kästchen = 52 Kalenderwochen ab Prognosebeginn. Farbskala: rot (viel Verkehr / schlecht zum Bauen) → gelb → grün (wenig Verkehr / gut zum Bauen). Das aktuell gewählte Zeitfenster wird mit einem dunklen Rahmen hervorgehoben. Tooltip bei Hover zeigt KW-Nummer und Score.

---

## Score-Berechnung

Der Eignungs-Score ist **relativ** normalisiert: Das beste gefundene Fenster erhält immer 99, das schlechteste immer 3. Ein Score von 99 bedeutet also nicht absolut „perfekt", sondern „am besten unter den gefundenen Optionen". Die Berechnung basiert auf einem gewichteten Disruptions-Score aus vier Komponenten (Gesamt-Verkehrsbelastung, Stauanteil, Spitzenstunden-Anteil, Lkw-Anteil).
