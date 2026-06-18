const BASE_URL = import.meta.env.VITE_API_URL ?? ''

export async function getSections() {
  const res = await fetch(`${BASE_URL}/sections`)
  if (!res.ok) throw new Error('getSections failed')
  return res.json() // { sections: SectionInfo[] }
}

export async function getRecommendations({ section, total_hours, filter = 'traffic', top_n = 3 }) {
  const res = await fetch(`${BASE_URL}/recommendations`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ section, total_hours, filter, top_n }),
  })
  if (!res.ok) throw new Error('getRecommendations failed')
  return res.json() // { windows: WindowResult[], kpi: KpiResult | null }
}

export async function getHeatmapData({ section, total_hours, filter = 'traffic' }) {
  const params = new URLSearchParams({ section, total_hours, filter })
  const res = await fetch(`${BASE_URL}/heatmap-data?${params}`)
  if (!res.ok) throw new Error('getHeatmapData failed')
  return res.json() // { weeks: HeatWeek[] }
}
