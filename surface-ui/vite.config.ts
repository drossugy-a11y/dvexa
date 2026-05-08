import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/surface': { target: 'http://localhost:8000', changeOrigin: true },
      '/ws/surface': { target: 'ws://localhost:8000', ws: true },
      '/task': { target: 'http://localhost:8000', changeOrigin: true },
      '/tasks': { target: 'http://localhost:8000', changeOrigin: true },
      '/health': { target: 'http://localhost:8000', changeOrigin: true },
    },
  },
})
