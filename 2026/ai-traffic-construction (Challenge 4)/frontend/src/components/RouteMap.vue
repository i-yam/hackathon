<template>
  <div class="route-map-wrapper">
    <iframe
      ref="iframeEl"
      src="/a3_karte.html"
      class="route-map"
      @load="onLoad"
    ></iframe>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'

const props = defineProps({
  activeSection: { type: Number, default: 0 },
})

const iframeEl = ref(null)
let ready = false

function sendSection(idx) {
  iframeEl.value?.contentWindow?.postMessage({ type: 'selectSection', section: idx }, '*')
}

function onLoad() {
  ready = true
  setTimeout(() => sendSection(props.activeSection), 300)
}

watch(() => props.activeSection, (val) => {
  if (ready) sendSection(val)
})
</script>

<style scoped>
.route-map-wrapper {
  height: 420px;
  border-radius: 8px;
  overflow: hidden;
}
.route-map {
  width: 100%;
  height: 100%;
  border: none;
  display: block;
}
</style>
