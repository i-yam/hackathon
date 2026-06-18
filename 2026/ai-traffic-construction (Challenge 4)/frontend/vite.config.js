import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    host: '0.0.0.0',
    port: 5173,
    watch: {
      usePolling: true
    },
    proxy: {
      '/sections':        { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/recommendations': { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/heatmap-data':    { target: 'http://127.0.0.1:8000', changeOrigin: true },
    }
  }
})
