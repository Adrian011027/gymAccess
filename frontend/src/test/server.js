import { setupServer } from 'msw/node'
import { http, HttpResponse } from 'msw'

/** Handlers por defecto: el gym vacío. Cada test declara lo que necesita encima. */
export const handlers = [
  http.get('/api/socios/', () => HttpResponse.json([])),
  http.get('/api/socios/planes/', () => HttpResponse.json([])),
  http.get('/api/socios/membresias/', () => HttpResponse.json([])),
  http.get('/api/socios/pagos/', () => HttpResponse.json([])),
  http.get('/api/socios/gastos/', () => HttpResponse.json([])),
  http.get('/api/gyms/sucursales/', () => HttpResponse.json([])),
  http.get('/api/gyms/clases/', () => HttpResponse.json([])),
  http.get('/api/gyms/equipamiento/', () => HttpResponse.json([])),
  http.get('/api/accesos/', () => HttpResponse.json([])),
  http.get('/api/accesos/stats/', () => HttpResponse.json({
    horarios_concurridos: [], accesos_hoy: 0, accesos_mes: 0,
  })),
  http.get('/api/notificaciones/', () => HttpResponse.json([])),
  http.get('/api/notificaciones/historial/', () => HttpResponse.json([])),
]

export const server = setupServer(...handlers)
