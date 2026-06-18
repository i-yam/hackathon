<template>
  <div class="dashboard">

    <!-- LOADING BAR -->
    <div class="loading-bar" v-if="loading"><div class="loading-bar-inner"></div></div>

    <!-- HEADER -->
    <header class="header">
      <div class="header-left">
        <div class="logo">A3</div>
        <div>
          <div class="title">Bau-Fenster-Planer</div>
          <div class="subtitle">A3 Bayern · Seligenstadt → Passau · Asphaltsanierung · 52-KW-Horizont</div>
        </div>
      </div>
    </header>

    <!-- ZONE 1: EINGABEN -->
    <div class="inputs-row">

      <!-- 01 Streckenabschnitt -->
      <div class="card" style="flex: 0 0 26%;">
        <div class="card-title"><span class="badge">01</span> Streckenabschnitt</div>
        <select class="select" :value="selectedSec" @change="setSection">
          <option v-for="s in sections" :key="s.id" :value="s.id">{{ s.name }}</option>
        </select>
        <div class="hint">Auch per Klick in der Karte wählbar ↓</div>
      </div>

      <!-- 02 Dauer -->
      <div class="card duration-card">
        <div class="card-title"><span class="badge">02</span> Geschätzte Bauphase</div>
        <div class="duration-presets">
          <button v-for="(p, i) in durationPresets" :key="p.label" class="preset-btn" :class="{ active: i === durPresetIdx && !customActive }" @click="setPreset(i)">{{ p.label }}</button>
          <button class="preset-btn" :class="{ active: customActive }" @click="customActive = true">Individuell</button>
        </div>
        <div v-if="customActive" class="custom-duration-row">
          <input class="custom-input" type="number" min="1" max="365" v-model.number="customDays" placeholder="Tage" />
          <span class="custom-label">Kalendertage Sperrzeit</span>
        </div>
        <div class="hint">Das Tool findet den optimalen Zeitraum für genau diese Bauphase.</div>
      </div>

      <!-- 03 Optimierungs-Ziel -->
      <div class="card" style="flex: 1;">
        <div class="card-title"><span class="badge">03</span> Optimierungs-Ziel</div>
        <div class="filter-options">
          <div v-for="f in filterOptions" :key="f.key" class="filter-option" :class="{ active: f.key === filter }" @click="setFilter(f.key)">
            <div class="filter-label">{{ f.label }}</div>
            <div class="filter-desc">{{ f.desc }}</div>
          </div>
        </div>
      </div>
    </div>

    <!-- ZONE 2: RESULT BANNER + KPIs side by side -->
    <div class="banner-kpi-row" :class="{ loading }">
      <div class="result-banner" v-if="activeWindow">
        <div class="banner-left">
          <span class="banner-tag" :class="activeWinIdx === 0 ? 'banner-tag--optimum' : ''">
            {{ activeWinIdx === 0 ? '✓ OPTIMALER ZEITRAUM' : 'ZEITFENSTER #' + (activeWinIdx + 1) }}
          </span>
          <div class="banner-period">{{ activeWindow.dates }}</div>
          <div class="banner-dates">{{ activeWindow.period }} · {{ bannerDuration }}</div>
        </div>
        <div class="banner-score-block">
          <div class="banner-score" :style="{ color: scoreColor(activeWindow.score) }">{{ activeWindow.score }}</div>
          <div class="banner-score-label">Eignungs-Score</div>
        </div>
        <div class="banner-right">
          <div class="banner-filter">{{ filterOptions.find(f => f.key === filter)?.label }}</div>
          <div class="banner-section">{{ sections.find(s => s.id === selectedSec)?.name }} · {{ sections.find(s => s.id === selectedSec)?.km }}</div>
        </div>
      </div>
      <div class="result-banner result-banner--error" v-else-if="error">
        <span class="banner-tag banner-tag--error">⚠ FEHLER</span>
        <div class="banner-period" style="font-size:14px; color:#b91c1c;">{{ error }}</div>
        <button class="retry-btn" @click="loadAll">Nochmal versuchen</button>
      </div>
      <div class="result-banner result-banner--empty" v-else-if="!loading && recommendations.windows.length === 0">
        <span class="banner-tag">KEINE ERGEBNISSE</span>
        <div class="banner-period" style="font-size:14px; color:#6b727a;">Für diese Kombination wurden keine geeigneten Zeitfenster gefunden.</div>
      </div>
      <div class="result-banner" v-else>
        <span class="banner-tag">{{ loading ? 'Lade Daten…' : '–' }}</span>
      </div>

      <div class="card kpi-card">
        <div class="card-title-sm" style="margin-bottom: 11px;">
          Kennzahlen · gewähltes Zeitfenster
          <span v-if="activeWinIdx === 0" class="optimum-badge">✓ Optimum</span>
          <span v-else class="compare-hint">Vergleich mit #1 (Optimum)</span>
        </div>
        <div class="kpi-row">
          <KpiTile :value="kpi ? kpi.mean_kfz_per_hour.toLocaleString('de-DE') : '—'" label="Ø Verkehr Kfz/h"
            :delta="kpiContext.kfz.delta" :isOptimum="activeWinIdx === 0" deltaUnit="Kfz/h" invertDelta />
          <KpiTile :value="kpi ? Math.round(kpi.mean_kfz_per_hour * kpi.lkw_share_pct / 100).toLocaleString('de-DE') : '—'" label="Ø Schwerlast Nfz/h"
            :delta="kpiContext.nfz.delta" :isOptimum="activeWinIdx === 0" deltaUnit="Nfz/h" invertDelta />
          <KpiTile :value="kpi ? kpi.lkw_share_pct + ' %' : '—'" label="Lkw-Anteil"
            :delta="kpiContext.lkw.delta" :isOptimum="activeWinIdx === 0" deltaUnit="%-Punkte" invertDelta />
        </div>
      </div>
    </div>

    <!-- MAIN: LEFT + RIGHT -->
    <div class="main-grid" :class="{ loading }">

      <!-- LEFT: nur Karte -->
      <div class="main-left">

        <!-- Geo-Karte -->
        <div class="card map-card" ref="mapCardRef">
          <div class="card-header">
            <span class="card-title-sm">Geo-Verlauf · A3 Bayern · Seligenstadt → Passau</span>
            <button class="btn-fullscreen" @click="openFullscreen" title="Vollbild">⛶</button>
          </div>
          <RouteMap :activeSection="selectedSec" />
        </div>
      </div>

      <!-- RIGHT -->
      <div class="main-right">

        <!-- Top-N Fenster -->
        <div class="card">
          <div class="card-header">
            <span class="card-title-sm">Top-{{ topN }} Bau-Fenster</span>
            <div class="topn-controls">
              <span class="card-hint" style="margin-right:8px;">Anzahl:</span>
              <button
                v-for="n in topNOptions" :key="n"
                class="preset-btn" :class="{ active: n === topN }"
                @click="topN = n; activeWinIdx = 0"
              >{{ n }}</button>
              <span class="card-hint" style="margin-left:12px;">Klick zum Auswählen</span>
            </div>
          </div>
          <div class="windows-list" ref="windowsListRef">
            <WindowCard
              v-for="(w, i) in topWindows" :key="w.rank"
              :rank="w.rank" :period="w.period" :dates="w.dates"
              :score="w.score" :active="w.active"
              @click="activeWinIdx = i"
            />
          </div>
        </div>

        <!-- Jahres-Heatmap -->
        <div class="card">
          <div class="card-header">
            <span class="card-title-sm">Jahres-Heatmap · 1 Kästchen = 1 Kalenderwoche</span>
            <span class="card-hint">▢ = gewähltes Fenster</span>
          </div>
          <div class="heatmap">
            <div
              v-for="w in heatmapWeeks" :key="w.kw"
              class="heatmap-cell"
              :class="{ 'heatmap-cell--clickable': w.windowIdx != null }"
              :style="{ background: w.color, boxShadow: w.selected ? 'inset 0 0 0 2px #14181c' : 'none' }"
              :title="w.tooltip"
              @click="onHeatmapClick(w)"
            ></div>
          </div>
          <div class="heatmap-legend">
            <span>Eignung:</span>
            <span class="legend-bar-sm"></span>
            <span>gering → hoch</span>
          </div>
        </div>
      </div>
    </div>

    <div class="footer">LightGBM-Prognose auf BASt-Zähldaten 2018–2023 · 52-KW-Horizont ab {{ horizonStart }} · A3 Bayern · Seligenstadt → Passau</div>
  </div>
</template>

<script setup>
import { ref, computed, watch, nextTick, onMounted, useTemplateRef } from 'vue'
import KpiTile from '../components/KpiTile.vue'
import WindowCard from '../components/WindowCard.vue'
import RouteMap from '../components/RouteMap.vue'
import { getSections, getRecommendations, getHeatmapData } from '../services/api.js'

// ── State ──────────────────────────────────────────────────────────────────
const mapCardRef      = useTemplateRef('mapCardRef')
const windowsListRef  = ref(null)
const sections     = ref([])
const selectedSec  = ref(0)
const activeWinIdx = ref(0)
const filter       = ref('traffic')
const durPresetIdx = ref(3) // default: 2 Wochen
const topN              = ref(3)
const topNOptions       = [3, 5, 10, 'Alle']
const pendingWeekSelect = ref(null)
const customActive = ref(false)
const customDays   = ref(14)
const horizonStart = ref('–')
const horizonStartDate = ref(null)

const recommendations = ref({ windows: [], kpi: null })
const heatWeeks       = ref([])
const loading         = ref(false)
const error           = ref(null)

// ── Config ─────────────────────────────────────────────────────────────────
const durationPresets = [
  { label: '1 Tag',    hours: 10 },
  { label: '3 Tage',   hours: 30 },
  { label: '1 Woche',  hours: 70 },
  { label: '2 Wochen', hours: 140 },
  { label: '4 Wochen', hours: 280 },
  { label: '8 Wochen', hours: 560 },
]

const filterOptions = [
  { key: 'traffic', label: 'Geringster Verkehrseinfluss', desc: 'wenigste betroffene Kfz' },
  { key: 'risk',    label: 'Min. Stau-/Unfallrisiko',     desc: 'wenigste Staus & Unfälle' },
  { key: 'freight', label: 'Schont Güter-/Pendlerverkehr', desc: 'wenig Lkw & Pendler' },
]

// ── Computed ────────────────────────────────────────────────────────────────
const totalHours  = computed(() => customActive.value ? ((customDays.value || 1) * 24) : durationPresets[durPresetIdx.value].hours)
const topWindows = computed(() =>
  recommendations.value.windows.map((w, i) => ({
    rank:  '#' + w.rank,
    period: w.period,
    dates:  w.dates,
    score:  w.score,
    active: i === activeWinIdx.value,
  }))
)
const activeWindow = computed(() => recommendations.value.windows[activeWinIdx.value] ?? null)

const bannerDuration = computed(() => {
  const w = activeWindow.value
  if (!w) return ''
  const days = w.week_span * 7
  if (days < 7) return `${days} Tage`
  if (days < 14) return '1 Woche'
  if (days % 7 === 0) return `${days / 7} Wochen`
  return `${days} Tage`
})

const kpiContext = computed(() => {
  const wins = recommendations.value.windows
  const w = activeWindow.value
  const best = wins[0]
  if (!w || !best || activeWinIdx.value === 0) return {
    kfz: { delta: null }, nfz: { delta: null }, lkw: { delta: null }
  }
  const bestNfz = Math.round(best.mean_kfz_per_hour * best.lkw_share_pct / 100)
  const curNfz  = Math.round(w.mean_kfz_per_hour * w.lkw_share_pct / 100)
  return {
    kfz: { delta: w.mean_kfz_per_hour - best.mean_kfz_per_hour },
    nfz: { delta: curNfz - bestNfz },
    lkw: { delta: parseFloat((w.lkw_share_pct - best.lkw_share_pct).toFixed(1)) },
  }
})
const kpi = computed(() => {
  const w = activeWindow.value
  if (!w) return recommendations.value.kpi
  const score = w.score
  const risk = score >= 68 ? 'niedrig' : score >= 46 ? 'mittel' : 'hoch'
  return {
    mean_kfz_per_hour: w.mean_kfz_per_hour,
    lkw_share_pct: w.lkw_share_pct,
    congestion_pct: w.congestion_pct,
    risk,
  }
})

const heatmapWeeks = computed(() =>
  heatWeeks.value.map(w => {
    const base = horizonStartDate.value
    const weekDate = base ? new Date(base.getTime() + w.week_index * 7 * 24 * 3600 * 1000) : null
    const kwNum = weekDate ? getISOWeek(weekDate) : w.week_index + 1
    const tooltip = `KW ${kwNum} · Score ${w.score}${w.month_label ? ' · ' + w.month_label : ''}`
    const windowIdx = recommendations.value.windows.findIndex(win =>
      w.week_index >= win.week_start && w.week_index < win.week_start + win.week_span
    )
    return {
      kw:        w.week_index,
      month:     w.month_label,
      color:     scoreToColor(w.score),
      tooltip,
      windowIdx: windowIdx >= 0 ? windowIdx : null,
      selected:  activeWindow.value
        ? w.week_index >= activeWindow.value.week_start &&
          w.week_index < activeWindow.value.week_start + activeWindow.value.week_span
        : false,
    }
  })
)

function getISOWeek(date) {
  const d = new Date(date)
  d.setHours(0, 0, 0, 0)
  d.setDate(d.getDate() + 4 - (d.getDay() || 7))
  const yearStart = new Date(d.getFullYear(), 0, 1)
  return Math.ceil((((d - yearStart) / 86400000) + 1) / 7)
}

// ── Helpers ─────────────────────────────────────────────────────────────────
function scoreToColor(sc) {
  const t = Math.max(0, Math.min(100, sc)) / 100
  const lerp = (a, b, x) => Math.round(a + (b - a) * x)
  const lo  = [224, 150, 142], mid = [240, 212, 138], hi = [150, 205, 170]
  const [r, g, b] = t < 0.5
    ? [lerp(lo[0], mid[0], t / 0.5), lerp(lo[1], mid[1], t / 0.5), lerp(lo[2], mid[2], t / 0.5)]
    : [lerp(mid[0], hi[0], (t - 0.5) / 0.5), lerp(mid[1], hi[1], (t - 0.5) / 0.5), lerp(mid[2], hi[2], (t - 0.5) / 0.5)]
  return `rgb(${r},${g},${b})`
}

// ── API Calls ────────────────────────────────────────────────────────────────
async function loadAll() {
  loading.value = true
  error.value   = null
  try {
    const [rec, heat] = await Promise.all([
      getRecommendations({ section: selectedSec.value, total_hours: totalHours.value, filter: filter.value, top_n: topN.value === 'Alle' ? 52 : topN.value }),
      getHeatmapData({ section: selectedSec.value, total_hours: totalHours.value, filter: filter.value }),
    ])
    recommendations.value = rec
    heatWeeks.value        = heat.weeks
    activeWinIdx.value     = 0
    selectPendingWeek()
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

function scoreColor(score) {
  // Continuous: 99=bright green, 80=yellow-green, 60=orange, <50=red
  const t = Math.max(0, Math.min(100, score)) / 100
  const lerp = (a, b, x) => Math.round(a + (b - a) * x)
  if (t >= 0.8) {
    const x = (t - 0.8) / 0.2
    return `rgb(${lerp(180,21,x)},${lerp(210,128,x)},${lerp(80,61,x)})`
  } else if (t >= 0.6) {
    const x = (t - 0.6) / 0.2
    return `rgb(${lerp(220,180,x)},${lerp(150,210,x)},${lerp(30,80,x)})`
  } else if (t >= 0.4) {
    const x = (t - 0.4) / 0.2
    return `rgb(${lerp(200,220,x)},${lerp(80,150,x)},20)`
  } else {
    return '#b91c1c'
  }
}

function onHeatmapClick(w) {
  pendingWeekSelect.value = w.kw
  if (topN.value !== 'Alle') {
    topN.value = 'Alle'  // triggers watcher → loadAll → selectPendingWeek
  } else {
    selectPendingWeek()
  }
}

function selectPendingWeek() {
  const wk = pendingWeekSelect.value
  if (wk == null) return
  pendingWeekSelect.value = null
  const idx = recommendations.value.windows.findIndex(win =>
    wk >= win.week_start && wk < win.week_start + win.week_span
  )
  if (idx !== -1) activeWinIdx.value = idx
}

function setPreset(i) { durPresetIdx.value = i; customActive.value = false }
function setFilter(key) { filter.value = key }
function setSection(e)  { selectedSec.value = Number(e.target.value) }

function openFullscreen() {
  const el = mapCardRef.value
  if (!el) return
  if (!document.fullscreenElement) el.requestFullscreen?.()
  else document.exitFullscreen?.()
}

// ── Lifecycle ────────────────────────────────────────────────────────────────
onMounted(async () => {
  const data = await getSections()
  sections.value       = data.sections
  selectedSec.value    = data.sections[0]?.id ?? 0
  if (data.horizon_start) {
    const d = new Date(data.horizon_start)
    horizonStartDate.value = d
    horizonStart.value = d.toLocaleDateString('de-DE', { day: '2-digit', month: '2-digit', year: '2-digit' })
  }
  await loadAll()
})

watch([selectedSec, durPresetIdx, filter, topN, customActive], loadAll)
watch(activeWinIdx, async (idx) => {
  await nextTick()
  const list = windowsListRef.value
  if (!list) return
  list.children[idx]?.scrollIntoView({ block: 'nearest', behavior: 'smooth' })
})
watch(customDays, () => { if (customActive.value && customDays.value > 0) loadAll() })
</script>

<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500&display=swap');

* { box-sizing: border-box; margin: 0; padding: 0; }
body { background: #eef0f2; font-family: 'IBM Plex Sans', Helvetica, Arial, sans-serif; color: #14181c; }
</style>

<style scoped>
.dashboard { min-height: 100vh; padding: 24px 28px 34px; }

/* HEADER */
.header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 20px; }
.header-left { display: flex; align-items: center; gap: 14px; }
.logo { width: 42px; height: 42px; border-radius: 10px; background: #14181c; color: #fff; display: flex; align-items: center; justify-content: center; font-weight: 700; font-size: 17px; }
.title { font-size: 22px; font-weight: 700; letter-spacing: -.3px; }
.subtitle { font-family: 'IBM Plex Mono', monospace; font-size: 12px; color: #6b727a; margin-top: 2px; }
.legend-pill { display: flex; align-items: center; gap: 10px; background: #fff; border: 1px solid #dfe3e7; border-radius: 11px; padding: 10px 14px; }
.legend-label { font-family: 'IBM Plex Mono', monospace; font-size: 10px; color: #9aa0a6; text-transform: uppercase; letter-spacing: .6px; }
.legend-bar { width: 120px; height: 9px; border-radius: 5px; background: linear-gradient(90deg, #e09690, #f0d48a, #96cdaa); }
.legend-text { font-size: 11px; color: #6b727a; }
.legend-arrow { font-family: 'IBM Plex Mono', monospace; font-size: 11px; color: #aeb4ba; }

/* CARDS */
.card { background: #fff; border: 1px solid #dfe3e7; border-radius: 14px; padding: 16px 18px; box-shadow: 0 1px 2px rgba(16,24,40,.04); }
.card-title { display: flex; align-items: center; gap: 8px; font-size: 13px; font-weight: 600; margin-bottom: 13px; }
.card-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 11px; }
.topn-controls { display: flex; align-items: center; gap: 5px; }
.card-title-sm { font-size: 12px; font-weight: 600; color: #515860; }
.card-hint { font-family: 'IBM Plex Mono', monospace; font-size: 10px; color: #aeb4ba; }
.badge { font-family: 'IBM Plex Mono', monospace; font-size: 11px; font-weight: 600; letter-spacing: .5px; color: #1f5da6; background: #eaf1fa; padding: 2px 7px; border-radius: 5px; }
.hint { font-family: 'IBM Plex Mono', monospace; font-size: 10px; color: #aeb4ba; margin-top: 9px; line-height: 1.4; }

/* INPUTS ROW */
.inputs-row { display: flex; gap: 16px; margin-bottom: 18px; align-items: stretch; }
.select { width: 100%; padding: 10px 12px; font-size: 15px; border: 1px solid #ccd2d8; border-radius: 9px; background: #fff; color: #14181c; font-family: 'IBM Plex Sans', sans-serif; }
.duration-card { min-height: 140px; }
.duration-presets { display: flex; flex-wrap: wrap; gap: 7px; }
.custom-duration-row { display: flex; align-items: center; gap: 8px; margin-top: 10px; }
.custom-input { width: 90px; padding: 7px 10px; border: 1px solid #1f5da6; border-radius: 7px; font-size: 14px; font-family: 'IBM Plex Sans', sans-serif; color: #14181c; outline: none; }
.custom-input:focus { box-shadow: 0 0 0 2px #eaf1fa; }
.custom-label { font-family: 'IBM Plex Mono', monospace; font-size: 11px; color: #6b727a; }
.preset-btn { padding: 6px 12px; border-radius: 7px; border: 1px solid #dfe3e7; background: #fff; font-size: 13px; cursor: pointer; font-family: 'IBM Plex Sans', sans-serif; color: #515860; }
.preset-btn.active { background: #eaf1fa; border-color: #1f5da6; color: #1f5da6; font-weight: 600; }
.filter-options { display: flex; gap: 9px; }
.filter-option { flex: 1; padding: 11px 13px; border-radius: 10px; border: 1px solid #dfe3e7; cursor: pointer; }
.filter-option.active { border: 1.5px solid #1f5da6; background: #eaf1fa; }
.filter-label { font-size: 14px; font-weight: 500; color: #14181c; line-height: 1.2; }
.filter-option.active .filter-label { font-weight: 600; color: #1f5da6; }
.filter-desc { font-family: 'IBM Plex Mono', monospace; font-size: 10px; color: #9aa0a6; margin-top: 4px; }

/* BANNER + KPI ROW */
.banner-kpi-row { display: flex; gap: 16px; margin-bottom: 20px; align-items: stretch; }
.result-banner { flex: 1; display: flex; align-items: center; gap: 16px; background: #fff; border: 1px solid #dfe3e7; border-radius: 14px; padding: 18px 20px; box-shadow: 0 1px 2px rgba(16,24,40,.04); min-width: 0; }
.kpi-card { flex: 1; min-width: 0; display: flex; flex-direction: column; justify-content: center; }
.banner-tag { font-family: 'IBM Plex Mono', monospace; font-size: 10px; font-weight: 600; color: #6b727a; letter-spacing: .5px; }
.banner-tag--optimum { color: #15803d; }
.banner-period { font-size: 17px; font-weight: 700; margin-top: 2px; }
.banner-dates { font-family: 'IBM Plex Mono', monospace; font-size: 11px; color: #6b727a; margin-top: 2px; }
.banner-score-block { margin-left: auto; flex-shrink: 0; text-align: center; }
.banner-score { font-size: 38px; font-weight: 700; transition: color .2s; line-height: 1; }
.banner-score-label { font-family: 'IBM Plex Mono', monospace; font-size: 9px; color: #9aa0a6; text-transform: uppercase; letter-spacing: .5px; margin-top: 3px; }
.banner-right { flex-shrink: 0; }
.banner-filter { font-size: 11px; color: #6b727a; }
.banner-section { font-size: 12px; font-weight: 600; margin-top: 2px; }
.optimum-badge { font-family: 'IBM Plex Mono', monospace; font-size: 10px; font-weight: 600; color: #15803d; background: #dcfce7; padding: 2px 8px; border-radius: 5px; margin-left: 8px; }
.compare-hint { font-family: 'IBM Plex Mono', monospace; font-size: 10px; color: #9aa0a6; margin-left: 8px; }
.banner-tag--error { color: #b91c1c !important; }
.result-banner--error { border-color: #fca5a5; background: #fff5f5; }
.result-banner--empty { border-color: #dfe3e7; background: #f9fafb; }
.retry-btn { margin-left: auto; padding: 7px 16px; border-radius: 8px; border: 1px solid #b91c1c; background: #fff; color: #b91c1c; font-size: 13px; font-family: 'IBM Plex Sans', sans-serif; cursor: pointer; font-weight: 500; }
.retry-btn:hover { background: #fff5f5; }

/* MAIN GRID */
.main-grid { display: flex; gap: 20px; align-items: flex-start; }
.main-left { flex: 0 0 50%; display: flex; flex-direction: column; gap: 16px; min-width: 0; }
.main-right { flex: 1; display: flex; flex-direction: column; gap: 16px; min-width: 0; }

/* MAP CARD */
.btn-fullscreen { background: none; border: 1px solid #dfe3e7; border-radius: 6px; padding: 3px 7px; font-size: 14px; cursor: pointer; color: #6b727a; line-height: 1; }
.btn-fullscreen:hover { background: #f5f7f9; color: #14181c; }
.map-card:fullscreen { background: #fff; padding: 12px; display: flex; flex-direction: column; border-radius: 0; }
.map-card:fullscreen :deep(.route-map-wrapper) { height: calc(100vh - 56px); border-radius: 4px; }
.map-card:fullscreen :deep(.route-map) { border-radius: 4px; }

/* KPI ROW */
.kpi-row { display: flex; gap: 10px; }
.kpi-row > * { flex: 1; min-width: 0; }

/* WINDOWS LIST */
.windows-list { display: flex; flex-direction: column; gap: 9px; height: 320px; overflow-y: auto; padding-right: 4px; }
.windows-list::-webkit-scrollbar { width: 5px; }
.windows-list::-webkit-scrollbar-track { background: transparent; }
.windows-list::-webkit-scrollbar-thumb { background: #dfe3e7; border-radius: 4px; }
.windows-list::-webkit-scrollbar-thumb:hover { background: #aeb4ba; }

/* HEATMAP */
.heatmap { display: flex; gap: 2px; }
.heatmap-cell { flex: 1; min-width: 0; height: 30px; border-radius: 2px; cursor: default; transition: opacity .1s; }
.heatmap-cell--clickable { cursor: pointer; }
.heatmap-cell--clickable:hover { opacity: 0.75; }
.heatmap-legend { display: flex; align-items: center; gap: 9px; margin-top: 14px; font-family: 'IBM Plex Mono', monospace; font-size: 10px; color: #9aa0a6; }
.legend-bar-sm { display: inline-block; width: 96px; height: 11px; border-radius: 3px; background: linear-gradient(90deg, #e09690, #f0d48a, #96cdaa); }

/* FOOTER */
.footer { font-family: 'IBM Plex Mono', monospace; font-size: 10px; color: #aeb4ba; margin-top: 20px; text-align: center; }

/* LOADING */
.loading-bar { position: fixed; top: 0; left: 0; right: 0; height: 3px; z-index: 9999; background: #dfe3e7; overflow: hidden; }
.loading-bar-inner { height: 100%; width: 40%; background: #1f5da6; border-radius: 0 2px 2px 0; animation: loadslide 1.2s ease-in-out infinite; }
@keyframes loadslide {
  0%   { transform: translateX(-100%); }
  100% { transform: translateX(300%); }
}
.banner-kpi-row.loading,
.main-grid.loading { opacity: 0.45; pointer-events: none; transition: opacity 0.15s; }
</style>
