import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    // Permite cualquier subdominio de ngrok (la URL gratis cambia en cada arranque).
    allowedHosts: ['.ngrok-free.app'],
    proxy: {
      '/api': 'http://localhost:8000',
    },
  },
})
