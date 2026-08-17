import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    // Permite cualquier subdominio de ngrok (la URL gratis cambia en cada arranque).
    allowedHosts: ['.ngrok-free.app', '.loca.lt'],
    proxy: {
      '/api': 'http://127.0.0.1:8001',
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: './src/test/setup.js',
    css: false,
    coverage: {
      provider: 'v8',
      include: ['src/**/*.{js,jsx}'],
      exclude: ['src/test/**', 'src/main.jsx', 'src/**/*.test.{js,jsx}'],
    },
  },
})
