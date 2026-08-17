import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterAll, afterEach, beforeAll, vi } from 'vitest'
import { server } from './server'

// Interceptor HTTP: los tests de componente corren sin backend levantado.
// `error` en onUnhandledRequest hace que una llamada no declarada rompa el test en vez
// de colgarse en silencio — si una pantalla pide algo que no esperábamos, queremos saberlo.
beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))

afterEach(() => {
  server.resetHandlers()
  cleanup()
  localStorage.clear()
  vi.clearAllMocks()
})

afterAll(() => server.close())

// jsdom no implementa matchMedia y CheckIn.jsx lo consulta al cargar el módulo
// para saber si está en una pantalla táctil.
if (!window.matchMedia) {
  window.matchMedia = query => ({
    matches: false,
    media: query,
    onchange: null,
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => false,
  })
}
