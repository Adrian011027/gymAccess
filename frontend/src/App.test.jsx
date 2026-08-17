/**
 * Matriz de rutas × roles: a dónde llega cada tipo de usuario y qué ve en el menú.
 *
 * Es el equivalente en el frontend a la matriz de permisos del backend. Si un guard se
 * rompe, aquí se nota antes de que alguien entre a una pantalla que no le toca.
 */
import { render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import App from './App'
import { iniciarSesion } from './test/utils'

// App monta su propio BrowserRouter, así que para controlar la ruta se prueban las
// piezas de dentro. Se renderiza App entera y se navega con el historial de jsdom.
function montar(ruta) {
  window.history.pushState({}, '', ruta)
  return render(<App />)
}

/** Rótulo visible y único de cada pantalla, para saber dónde aterrizamos. */
const MARCAS = {
  '/checkin': /control de acceso/i,
  '/dashboard': /dashboard/i,
  '/clases': /clases/i,
  '/login': /iniciar sesión/i,
}

const DESTINOS = {
  superadmin: { inicio: '/dashboard', pagos: true, admin: true },
  admin: { inicio: '/dashboard', pagos: true, admin: true },
  recepcion: { inicio: '/checkin', pagos: true, admin: false },
  coach: { inicio: '/clases', pagos: false, admin: false },
}

describe('sesión', () => {
  it('sin token, cualquier ruta protegida manda a login', async () => {
    montar('/socios')
    expect(await screen.findByText(MARCAS['/login'])).toBeInTheDocument()
  })

  it('un token corrupto no deja la pantalla en blanco: manda a login', async () => {
    localStorage.setItem('access', 'basura-que-no-es-un-jwt')
    montar('/dashboard')
    expect(await screen.findByText(MARCAS['/login'])).toBeInTheDocument()
  })
})

describe.each(Object.entries(DESTINOS))('rol %s', (rol, esperado) => {
  it(`aterriza en ${esperado.inicio} desde la raíz`, async () => {
    iniciarSesion(rol)
    montar('/')
    await waitFor(() => {
      expect(window.location.pathname).toBe(esperado.inicio)
    })
  })

  it(`una ruta inexistente lo devuelve a ${esperado.inicio}`, async () => {
    iniciarSesion(rol)
    montar('/ruta-que-no-existe')
    await waitFor(() => {
      expect(window.location.pathname).toBe(esperado.inicio)
    })
  })

  it(`${esperado.admin ? 'entra a' : 'es rebotado de'} /reportes`, async () => {
    iniciarSesion(rol)
    montar('/reportes')
    await waitFor(() => {
      expect(window.location.pathname).toBe(esperado.admin ? '/reportes' : esperado.inicio)
    })
  })

  it(`${esperado.admin ? 'entra a' : 'es rebotado de'} /configuracion`, async () => {
    iniciarSesion(rol)
    montar('/configuracion')
    await waitFor(() => {
      expect(window.location.pathname).toBe(esperado.admin ? '/configuracion' : esperado.inicio)
    })
  })

  it(`${esperado.pagos ? 'entra a' : 'es rebotado de'} /pagos`, async () => {
    iniciarSesion(rol)
    montar('/pagos')
    await waitFor(() => {
      expect(window.location.pathname).toBe(esperado.pagos ? '/pagos' : esperado.inicio)
    })
  })

  it('siempre puede entrar a /checkin', async () => {
    iniciarSesion(rol)
    montar('/checkin')
    await waitFor(() => {
      expect(window.location.pathname).toBe('/checkin')
    })
  })
})

describe('menú lateral', () => {
  const enlaces = () => screen.getAllByRole('link').map(a => a.textContent.trim())

  it('el admin ve los 8 módulos', async () => {
    iniciarSesion('admin')
    montar('/dashboard')
    await screen.findByRole('link', { name: /dashboard/i })
    expect(enlaces()).toHaveLength(8)
  })

  it('recepción no ve los módulos de admin, pero sí Pagos', async () => {
    iniciarSesion('recepcion')
    montar('/checkin')
    await screen.findByRole('link', { name: /check-in/i })
    const menu = enlaces()
    expect(menu).toContain('Pagos')
    expect(menu).not.toContain('Dashboard')
    expect(menu).not.toContain('Reportes')
    expect(menu).not.toContain('Configuración')
    expect(menu).not.toContain('Equipamiento')
  })

  it('el coach no ve Pagos: no toca la caja', async () => {
    iniciarSesion('coach')
    montar('/clases')
    await screen.findByRole('link', { name: /clases/i })
    const menu = enlaces()
    expect(menu).not.toContain('Pagos')
    expect(menu).not.toContain('Dashboard')
    expect(menu).toContain('Clases')
    expect(menu).toContain('Check-In')
  })

  it('el menú nunca ofrece un link al que ese rol no puede entrar', async () => {
    iniciarSesion('coach')
    montar('/clases')
    await screen.findByRole('link', { name: /clases/i })
    const prohibidas = ['Dashboard', 'Reportes', 'Configuración', 'Equipamiento', 'Pagos']
    for (const label of enlaces()) {
      expect(prohibidas).not.toContain(label)
    }
  })
})
