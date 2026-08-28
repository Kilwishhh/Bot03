import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
      '/auth': { target: 'http://localhost:8000', changeOrigin: true },
      '/strategies': { target: 'http://localhost:8000', changeOrigin: true },
      '/signals': { target: 'http://localhost:8000', changeOrigin: true },
      '/followups': { target: 'http://localhost:8000', changeOrigin: true },
      '/automation': { target: 'http://localhost:8000', changeOrigin: true },
      '/connections': { target: 'http://localhost:8000', changeOrigin: true },
      '/publishing': { target: 'http://localhost:8000', changeOrigin: true },
      '/emergency': { target: 'http://localhost:8000', changeOrigin: true },
      '/admin': { target: 'http://localhost:8000', changeOrigin: true },
      '/me': { target: 'http://localhost:8000', changeOrigin: true },
      '/health': { target: 'http://localhost:8000', changeOrigin: true },
    },
  },
});
