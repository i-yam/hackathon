<template>
  <div class="kpi-tile">
    <div class="kpi-value" :class="[valueClass, altValueClass]">
      <span v-if="riskIcon" class="risk-icon">{{ riskIcon }}</span>{{ value }}<span v-if="deltaArrow && !isOptimum" class="inline-arrow" :class="deltaClass">{{ deltaArrow }}</span>
    </div>
    <div class="kpi-label">{{ label }}</div>
    <div v-if="isOptimum" class="kpi-optimum">✓ Bestes Fenster</div>
    <div v-else-if="delta != null" class="kpi-delta" :class="deltaClass">{{ deltaFormatted }}</div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  value:       { type: String, default: '—' },
  label:       { type: String, default: '' },
  risk:        { type: String, default: null },
  delta:       { type: Number, default: null },
  deltaUnit:   { type: String, default: '' },
  invertDelta: { type: Boolean, default: false }, // true = positive delta = schlechter
  isOptimum:   { type: Boolean, default: false },
})

const riskIcon = computed(() => {
  if (!props.risk) return null
  return props.risk === 'niedrig' ? '✓ ' : '⚠ '
})
const valueClass = computed(() => {
  if (!props.risk) return ''
  return props.risk === 'niedrig' ? 'risk-low' : props.risk === 'mittel' ? 'risk-mid' : 'risk-high'
})

const altValueClass = computed(() => {
  if (props.isOptimum || props.delta == null || props.risk) return ''
  return props.delta === 0 ? '' : (props.invertDelta ? (props.delta > 0 ? 'delta-bad' : 'delta-good') : (props.delta < 0 ? 'delta-bad' : 'delta-good'))
})

const deltaArrow = computed(() => {
  if (props.delta == null || props.delta === 0) return ''
  return props.delta > 0 ? '↑' : '↓'
})

const deltaFormatted = computed(() => {
  if (props.delta == null) return ''
  const sign = props.delta > 0 ? '+' : '−'
  const abs = Math.abs(props.delta)
  return `${sign}${abs} ${props.deltaUnit} vs. Optimum`
})

const deltaClass = computed(() => {
  if (props.delta == null || props.delta === 0) return 'delta-neutral'
  const worse = props.invertDelta ? props.delta > 0 : props.delta < 0
  return worse ? 'delta-bad' : 'delta-good'
})
</script>

<style scoped>
.kpi-tile {
  background: #f4f5f6;
  border-radius: 10px;
  padding: 14px 16px;
  min-width: 0;
}
.kpi-value {
  font-size: 22px;
  font-weight: 700;
  color: #14181c;
  line-height: 1.1;
}
.kpi-label {
  font-family: 'IBM Plex Mono', monospace;
  font-size: 10px;
  color: #9aa0a6;
  margin-top: 5px;
}
.risk-icon { font-size: 16px; }
.risk-low  { color: #15803d; }
.risk-mid  { color: #b45309; }
.risk-high { color: #b91c1c; }

.kpi-optimum {
  font-family: 'IBM Plex Mono', monospace;
  font-size: 10px;
  color: #15803d;
  margin-top: 6px;
  font-weight: 600;
}
.kpi-delta {
  font-family: 'IBM Plex Mono', monospace;
  font-size: 10px;
  margin-top: 6px;
  font-weight: 500;
}
.delta-good    { color: #15803d; }
.delta-bad     { color: #b91c1c; }
.delta-neutral { color: #9aa0a6; }
.inline-arrow  { font-size: 18px; margin-left: 3px; vertical-align: middle; }
</style>
