import process from 'node:process'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    // Permite cualquier subdominio de ngrok (la URL gratis cambia en cada arranque).
    allowedHosts: ['.ngrok-free.app', '.loca.lt'],
    proxy: {
      // 8001 por defecto: el 8000 lo ocupa el backend del SaaS de spas
      // (`saas_agenda_backend`), que corre en la misma máquina. Se puede apuntar a
      // otro sitio con VITE_API_PROXY sin tocar este archivo —por ejemplo al
      // `manage.py runserver` de siempre en el 8000, si se trabaja sin Docker—.
      '/api': process.env.VITE_API_PROXY || 'http://127.0.0.1:8001',
    },
  },
})
