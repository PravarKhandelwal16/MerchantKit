import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [
    tailwindcss(),
    react(),
  ],
  server: {
    port: 5173,
    proxy: {
      '/health': 'http://127.0.0.1:8000',
      '/agent': 'http://127.0.0.1:8000',
      '/tools': 'http://127.0.0.1:8000',
      '/payment': 'http://127.0.0.1:8000',
      '/dashboard': 'http://127.0.0.1:8000',
    },
  },
})
