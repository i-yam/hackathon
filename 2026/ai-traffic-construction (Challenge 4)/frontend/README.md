# Vue 3 Frontend

Vue 3 + Vite Entwicklungsumgebung in Docker mit Hot Reload.

## Voraussetzungen

- [Docker](https://www.docker.com/) + Docker Compose

## Starten

```bash
docker compose up --build
```

App läuft unter: **http://localhost:5173**

Änderungen an Dateien im `src/`-Ordner werden sofort im Browser aktualisiert (Hot Reload) — kein Neustart nötig.

## Projektstruktur

```
vue-frontend/
├── src/
│   ├── App.vue          # Root-Komponente
│   ├── main.js          # Einstiegspunkt
│   └── components/      # Eigene Komponenten hier ablegen
├── index.html
├── vite.config.js
├── Dockerfile
└── docker-compose.yml
```

## Neue Komponenten

Komponenten in `src/components/` ablegen und in `App.vue` importieren:

```vue
<script setup>
import MeineKomponente from './components/MeineKomponente.vue'
</script>
```

## Produktions-Build (ohne Docker)

```bash
npm install
npm run build
# Output liegt in dist/
```
