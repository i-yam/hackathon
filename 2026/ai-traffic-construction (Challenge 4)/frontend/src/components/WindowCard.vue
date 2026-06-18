<template>
  <div class="window-card" :class="{ active, optimum: rank === '#1' && !active }">
    <div class="window-rank">{{ rank }}</div>
    <div class="window-info">
      <div class="window-period">{{ period }}</div>
      <div class="window-dates">{{ dates }}</div>
    </div>
    <div class="window-score" :style="{ color: scoreColor }">{{ score }}</div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  rank:   { type: String, default: '#1' },
  period: { type: String, default: '—' },
  dates:  { type: String, default: '—' },
  score:  { type: Number, default: 0 },
  active: { type: Boolean, default: false },
})

const scoreColor = computed(() => {
  const t = Math.max(0, Math.min(100, props.score)) / 100
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
})
</script>

<style scoped>
.window-card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 14px;
  border-radius: 10px;
  border: 1px solid #dfe3e7;
  cursor: pointer;
  transition: all .12s ease;
}
.window-card.optimum {
  border-color: #16a34a;
  background: #f0fdf4;
}
.window-card.active {
  border-color: #1f5da6;
  background: #eaf1fa;
}
.window-rank {
  font-family: 'IBM Plex Mono', monospace;
  font-size: 11px;
  font-weight: 600;
  color: #9aa0a6;
  min-width: 24px;
}
.window-info {
  flex: 1;
  min-width: 0;
}
.window-period {
  font-size: 13px;
  font-weight: 600;
  color: #14181c;
}
.window-dates {
  font-family: 'IBM Plex Mono', monospace;
  font-size: 10px;
  color: #9aa0a6;
  margin-top: 2px;
}
.window-score {
  font-size: 20px;
  font-weight: 700;
  min-width: 32px;
  text-align: right;
}
</style>
