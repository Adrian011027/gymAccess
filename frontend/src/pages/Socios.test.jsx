/**
 * La pantalla más usada del sistema y la que estaba peor cubierta (3.67%).
 *
 * Da de alta socios, les genera el QR con el que van a entrar por la puerta y sincroniza
 * huellas. Un alta a medias deja a alguien pagando sin poder entrar.
 */
import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { afterEach, describe, expect, it, vi } from 'vitest'
import Socios from './Socios'
import { server } from '../test/server'
import { renderConSesion } from '../test/utils'

const SOCIOS = [
  {
    id: 1, nombre: 'Ana', apellido: 'Lopez', email: 'ana@x.com', telefono: '555',
    activo: true, creado_en: '2025-01-15T10:00:00Z', codigo_acceso: 'R3B-QR-00001-1234',
    membresia_activa: { id: 1, plan: 'Mensual', fecha_fin: '2026-09-24', estado: 'activa' },
  },
  {
    id: 2, nombre: 'Luis', apellido: 'Diaz', email: '', telefono: '',
    activo: false, creado_en: '2024-06-01T10:00:00Z', codigo_acceso: 'R3B-QR-00002-5678',
    membresia_activa: null,
  },
]

const PLANES = [
  { id: 10, nombre: 'Mensual', tipo: 'mensual', precio: '500.00', duracion_dias: 30 },
]
const SUCURSALES = [{ id: 1, nombre: 'Matriz' }]

function datos({ socios = SOCIOS, planes = PLANES, sucursales = SUCURSALES } = {}) {
  server.use(
    http.get('/api/socios/', () => HttpResponse.json(socios)),
    http.get('/api/socios/planes/', () => HttpResponse.json(planes)),
    http.get('/api/gyms/sucursales/', () => HttpResponse.json(sucursales)),
  )
}

const montar = (rol = 'admin') => renderConSesion(<Socios />, { rol, ruta: '/socios' })

afterEach(() => {
  delete window.fingerprintAgent
})

describe('listado', () => {
  it('muestra los socios cargados', async () => {
    datos()
    montar()
    expect(await screen.findByText(/Ana/)).toBeInTheDocument()
    expect(screen.getByText(/Luis/)).toBeInTheDocument()
  })

  it('incluye tanto activos como dados de baja', async () => {
    datos()
    montar()
    await screen.findByText(/Ana/)
    // Un socio inactivo que desaparece de la lista es un socio que nadie cobra.
    expect(screen.getByText(/Luis/)).toBeInTheDocument()
  })

  it('gym vacío no muestra NaN ni undefined', async () => {
    datos({ socios: [] })
    montar()
    await waitFor(() => {
      expect(screen.queryByText(/NaN|undefined/)).not.toBeInTheDocument()
    })
  })

  it('si falla la carga, la pantalla no se rompe', async () => {
    server.use(
      http.get('/api/socios/', () => HttpResponse.error()),
      http.get('/api/socios/planes/', () => HttpResponse.json([])),
      http.get('/api/gyms/sucursales/', () => HttpResponse.json([])),
    )
    montar()
    await waitFor(() => {
      expect(screen.queryByText(/NaN|undefined/)).not.toBeInTheDocument()
    })
  })
})

describe('buscador', () => {
  const buscador = () => screen.getByPlaceholderText(/buscar/i)

  it('filtra por nombre', async () => {
    datos()
    const user = userEvent.setup()
    montar()
    await screen.findByText(/Ana/)
    await user.type(buscador(), 'Ana')

    await waitFor(() => expect(screen.queryByText(/Luis/)).not.toBeInTheDocument())
    expect(screen.getByText(/Ana/)).toBeInTheDocument()
  })

  it('filtra por apellido', async () => {
    datos()
    const user = userEvent.setup()
    montar()
    await screen.findByText(/Ana/)
    await user.type(buscador(), 'Diaz')

    await waitFor(() => expect(screen.queryByText(/Ana/)).not.toBeInTheDocument())
  })

  it('sin coincidencias no rompe la tabla', async () => {
    datos()
    const user = userEvent.setup()
    montar()
    await screen.findByText(/Ana/)
    await user.type(buscador(), 'zzzzznoexiste')

    await waitFor(() => expect(screen.queryByText(/Ana/)).not.toBeInTheDocument())
  })
})

describe('alta de socio', () => {
  async function abrirFormulario(user) {
    await user.click(await screen.findByRole('button', { name: /nuevo socio/i }))
    await user.type(await screen.findByLabelText(/^nombre$/i), 'Sara')
    await user.type(screen.getByLabelText(/apellido/i), 'Ruiz')
  }

  it('crea el socio y le asigna la membresía del plan elegido', async () => {
    const llamadas = []
    datos()
    server.use(
      http.post('/api/socios/', async ({ request }) => {
        llamadas.push(['socio', await request.json()])
        return HttpResponse.json({ id: 3, nombre: 'Sara' }, { status: 201 })
      }),
      http.post('/api/socios/membresias/', async ({ request }) => {
        llamadas.push(['membresia', await request.json()])
        return HttpResponse.json({ id: 5 }, { status: 201 })
      }),
    )
    const user = userEvent.setup()
    montar()
    await abrirFormulario(user)
    await user.selectOptions(screen.getByLabelText(/^plan$/i), '10')
    await user.click(screen.getByRole('button', { name: /^guardar$/i }))

    await waitFor(() => expect(llamadas).toHaveLength(2))
    expect(llamadas[0][0]).toBe('socio')
    expect(llamadas[1][0]).toBe('membresia')
    expect(llamadas[1][1]).toMatchObject({ socio: 3, plan: '10', sucursal: 1 })
  })

  it('sin plan elegido sólo crea el socio, sin membresía', async () => {
    const llamadas = []
    datos()
    server.use(
      http.post('/api/socios/', async () => {
        llamadas.push('socio')
        return HttpResponse.json({ id: 3 }, { status: 201 })
      }),
      http.post('/api/socios/membresias/', async () => {
        llamadas.push('membresia')
        return HttpResponse.json({ id: 5 }, { status: 201 })
      }),
    )
    const user = userEvent.setup()
    montar()
    await abrirFormulario(user)
    await user.click(screen.getByRole('button', { name: /^guardar$/i }))

    await waitFor(() => expect(llamadas).toEqual(['socio']))
  })

  it('si el alta falla, el modal no se cierra y no se pierde lo escrito', async () => {
    datos()
    server.use(http.post('/api/socios/', () =>
      HttpResponse.json({ error: 'nel' }, { status: 400 })))
    const user = userEvent.setup()
    montar()
    await abrirFormulario(user)
    await user.click(screen.getByRole('button', { name: /^guardar$/i }))

    await waitFor(() => {
      expect(screen.getByDisplayValue('Sara')).toBeInTheDocument()
    })
  })
})

describe('código QR', () => {
  it('muestra el código de acceso del socio', async () => {
    datos()
    montar()
    await screen.findByText(/Ana/)
    expect(screen.getByText(/R3B-QR-00001-1234/)).toBeInTheDocument()
  })

  it('un socio sin código no rompe el render', async () => {
    datos({ socios: [{ ...SOCIOS[0], codigo_acceso: null }] })
    montar()
    await screen.findByText(/Ana/)
    expect(screen.queryByText(/NaN|undefined/)).not.toBeInTheDocument()
  })
})

describe('sincronizar huella', () => {
  async function abrirHuella(user) {
    await screen.findByText(/Ana/)
    const botones = screen.getAllByRole('button', { name: /huella/i })
    await user.click(botones[0])
  }

  it('sin el agente instalado avisa en vez de fallar en silencio', async () => {
    datos()
    const user = userEvent.setup()
    montar()
    await abrirHuella(user)
    await user.click(screen.getByRole('button', { name: /capturar|iniciar/i }))

    expect(await screen.findByText(/agente de huella no detectado/i)).toBeInTheDocument()
  })

  it('con el agente presente sincroniza y confirma', async () => {
    datos()
    window.fingerprintAgent = { capturar: vi.fn().mockResolvedValue('TEMPLATE-ABC') }
    server.use(http.post('/api/accesos/sincronizar-huella/', () =>
      HttpResponse.json({ id: 1, tipo: 'huella', token: 'TEMPLATE-ABC' })))
    const user = userEvent.setup()
    montar()
    await abrirHuella(user)
    await user.click(screen.getByRole('button', { name: /capturar|iniciar/i }))

    expect(await screen.findByText(/sincronizada correctamente/i)).toBeInTheDocument()
  })

  it('una huella ya registrada a otro socio muestra el conflicto', async () => {
    datos()
    window.fingerprintAgent = { capturar: vi.fn().mockResolvedValue('TEMPLATE-ABC') }
    server.use(http.post('/api/accesos/sincronizar-huella/', () =>
      HttpResponse.json({ error: 'Esta huella ya está registrada a otro socio' }, { status: 409 })))
    const user = userEvent.setup()
    montar()
    await abrirHuella(user)
    await user.click(screen.getByRole('button', { name: /capturar|iniciar/i }))

    expect(await screen.findByText(/ya está registrada a otro socio/i)).toBeInTheDocument()
  })
})
