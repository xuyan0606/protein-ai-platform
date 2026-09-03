import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import path from 'path'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  build: {
    chunkSizeWarningLimit: 1500,
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes('node_modules/recharts')) return 'vendor-charts'
          if (id.includes('node_modules/react') || id.includes('node_modules/react-dom')) return 'vendor-react'
        },
      },
    },
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    host: '0.0.0.0',
    port: 3000,
    proxy: {
      '^/wiki/': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '^/auth/': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '^/static/': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '^/fonts/': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '^/images/': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '^/realtime/': {
        target: 'ws://localhost:8000',
        changeOrigin: true,
        ws: true,
      },
      '^/\\.well-known/': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
