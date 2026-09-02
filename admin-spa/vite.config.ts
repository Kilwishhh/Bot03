import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  base: '/admin/',
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/auth': { target: 'http://localhost:8000', changeOrigin: true },
      '/admin': { target: 'http://localhost:8000', changeOrigin: true },
      '/signals': { target: 'http://localhost:8000', changeOrigin: true },
      '/positions': { target: 'http://localhost:8000', changeOrigin: true },
      '/trades': { target: 'http://localhost:8000', changeOrigin: true },
      '/me': { target: 'http://localhost:8000', changeOrigin: true },
      '/dashboard': { target: 'http://localhost:8000', changeOrigin: true },
      '/user': { target: 'http://localhost:8000', changeOrigin: true },
      '/paper-config': { target: 'http://localhost:8000', changeOrigin: true },
    },
  },
})