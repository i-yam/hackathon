# A3 Bau-Fenster-Planer

Interaktives Dashboard zur Planung optimaler Bau-Zeitfenster auf der BAB A3 (Seligenstadt → Passau).

Ein LightGBM-Modell prognostiziert den stündlichen Verkehr für 52 Wochen auf Basis von BASt-Zähldaten 2018–2023. Die App berechnet daraus einen Eignungs-Score je Kalenderwoche und empfiehlt die verkehrsärmsten Zeitfenster für Straßensperrungen.

---

## Schnellstart (empfohlen: Docker)

### Voraussetzungen

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) installiert und gestartet
- Verzeichnisse `data_clean/` und `models/` im Projektordner vorhanden (nicht im Repo enthalten)

### Starten

```bash
docker compose up --build
```

Das startet **Backend und Frontend gleichzeitig**. Beim ersten Start werden Abhängigkeiten geladen (~2–3 Min).

| Dienst   | URL                         |
|----------|-----------------------------|
| Frontend | http://localhost            |
| Backend  | http://localhost:8000/docs  |

### Stoppen

```bash
docker compose down
```

### Neu ziehen & starten

```bash
docker compose up --build
```

---

## Projektstruktur

```
.
├── api.py                  # FastAPI-App (3 Endpunkte)
├── schemas.py              # Pydantic-Modelle
├── recommend_windows.py    # Kern-Logik: Prognose + Scoring
├── forecast_lgbm.py        # LightGBM-Wrapper
├── requirements.txt
├── Dockerfile              # Backend-Image
├── docker-compose.yml      # Startet Backend + Frontend zusammen
│
├── frontend/               # Vue 3 + Vite
│   ├── src/
│   │   ├── views/HomeView.vue
│   │   ├── components/
│   │   │   ├── RouteMap.vue
│   │   │   ├── WindowCard.vue
│   │   │   └── KpiTile.vue
│   │   └── services/api.js
│   ├── Dockerfile          # Frontend-Image
│   └── docker-compose.yml
│
├── data_clean/             # Parquet-Partitionen (nicht im Repo)
├── models/                 # LightGBM-Modell + Metadaten (nicht im Repo)
│
├── UI_GUIDE.md             # Dokumentation der Benutzeroberfläche
└── README.md
```

---

## API-Endpunkte

| Methode | Pfad | Beschreibung |
|---------|------|--------------|
| `GET`  | `/sections` | 5 A3-Abschnitte + Prognosebeginn |
| `POST` | `/recommendations` | Top-N Bau-Fenster für Abschnitt, Dauer und Filter |
| `GET`  | `/heatmap-data` | 52-Wochen-Eignungs-Scores für die Heatmap |

Vollständige Spezifikation: http://localhost:8000/docs

---

## Lokale Entwicklung (ohne Docker)

<details>
<summary>Backend</summary>

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 -m uvicorn old.api:app --port 8000 --reload
```
</details>

<details>
<summary>Frontend</summary>

```bash
cd frontend
npm install
npm run dev
```

Frontend läuft auf http://localhost:5173 — der Vite-Dev-Server leitet API-Anfragen per Proxy an das Backend weiter.
</details>
