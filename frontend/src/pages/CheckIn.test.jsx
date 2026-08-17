/**
 * El kiosco. Es la pantalla que va a operar el lector QR, y la única que usa gente que
 * no es empleada del gym, así que no puede colgarse ni quedarse en un estado raro.
 *
 * El lector se comporta como un teclado: "teclea" el código y manda Enter. Por eso lo
 * que se prueba aquí es el envío por Enter, la limpieza del input entre escaneos y el
 * regreso del foco — si algo de eso se rompe, el segundo socio de la fila no puede entrar.
 */
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import CheckIn from './CheckIn'
import { server } from '../test/server'

const SUCURSALES = [
  { id: 1, nombre: 'Matriz', gym: 1 },
  { id: 2, nombre: 'Sucursal Norte', gym: 1 },
]

function conSucursales(lista = SUCURSALES) {
  server.use(http.get('/api/gyms/sucursales/', () => HttpResponse.json(lista)))
}

function permitido(datos = {}) {
  server.use(http.post('/api/accesos/checkin/', () => HttpResponse.json({
    acceso: 'permitido',
    socio: 'Ana Lopez',
    foto: null,
    plan: 'Mensual',
    vence: '2026-09-24',
    repetido: false,
    ...datos,
  })))
}

function denegado(datos = {}, code = 403) {
  server.use(http.post('/api/accesos/checkin/', () => HttpResponse.json({
    acceso: 'denegado', socio: 'Ana Lopez', motivo: 'membresía no activa', ...datos,
  }, { status: code })))
}

const input = () => screen.getByPlaceholderText(/código de acceso/i)

/** Simula un escaneo: el lector teclea el código y manda Enter. */
async function escanear(user, codigo) {
  await user.type(input(), `${codigo}{Enter}`)
}

beforeEach(() => {
  conSucursales()
  vi.useRealTimers()
})

afterEach(() => vi.useRealTimers())

describe('carga inicial', () => {
  it('preselecciona la primera sucursal', async () => {
    render(<CheckIn />)
    await waitFor(() => {
      expect(screen.getByRole('combobox')).toHaveValue('1')
    })
  })

  it('sin sucursales muestra el aviso y no revienta', async () => {
    conSucursales([])
    render(<CheckIn />)
    expect(await screen.findByText(/sin sucursales/i)).toBeInTheDocument()
  })

  it('si falla la carga de sucursales la pantalla sigue en pie', async () => {
    server.use(http.get('/api/gyms/sucursales/', () => HttpResponse.error()))
    render(<CheckIn />)
    expect(await screen.findByText(/control de acceso/i)).toBeInTheDocument()
  })
})

describe('acceso permitido', () => {
  it('muestra la bienvenida con nombre, plan y vencimiento', async () => {
    const user = userEvent.setup()
    permitido()
    render(<CheckIn />)
    await escanear(user, 'R3B-QR-00001-1234')

    expect(await screen.findByText(/bienvenido/i)).toBeInTheDocument()
    expect(screen.getByText('Ana Lopez')).toBeInTheDocument()
    expect(screen.getByText('Mensual')).toBeInTheDocument()
    expect(screen.getByText('2026-09-24')).toBeInTheDocument()
  })

  it('sin fecha de vencimiento dice "Sin fecha límite", no undefined', async () => {
    const user = userEvent.setup()
    permitido({ vence: null })
    render(<CheckIn />)
    await escanear(user, 'TOKEN')

    expect(await screen.findByText(/sin fecha límite/i)).toBeInTheDocument()
  })

  it('limpia el input después del escaneo, listo para el siguiente socio', async () => {
    const user = userEvent.setup()
    permitido()
    render(<CheckIn />)
    await escanear(user, 'TOKEN')

    await screen.findByText(/bienvenido/i)
    expect(input()).toHaveValue('')
  })

  it('el foco vuelve al input para que el lector siga funcionando', async () => {
    const user = userEvent.setup()
    permitido()
    render(<CheckIn />)
    await escanear(user, 'TOKEN')

    await screen.findByText(/bienvenido/i)
    await waitFor(() => expect(input()).toHaveFocus())
  })

  it('recorta espacios del código antes de enviarlo', async () => {
    const user = userEvent.setup()
    let recibido
    server.use(http.post('/api/accesos/checkin/', async ({ request }) => {
      recibido = await request.json()
      return HttpResponse.json({ acceso: 'permitido', socio: 'Ana', plan: 'M', vence: null })
    }))
    render(<CheckIn />)
    await escanear(user, '  TOKEN123  ')

    await waitFor(() => expect(recibido?.token).toBe('TOKEN123'))
  })

  it('manda la sucursal seleccionada, no siempre la primera', async () => {
    const user = userEvent.setup()
    let recibido
    server.use(http.post('/api/accesos/checkin/', async ({ request }) => {
      recibido = await request.json()
      return HttpResponse.json({ acceso: 'permitido', socio: 'Ana', plan: 'M', vence: null })
    }))
    render(<CheckIn />)
    await waitFor(() => expect(screen.getByRole('combobox')).toHaveValue('1'))
    await user.selectOptions(screen.getByRole('combobox'), '2')
    await escanear(user, 'TOKEN')

    await waitFor(() => expect(recibido?.sucursal_id).toBe('2'))
  })
})

describe('acceso denegado', () => {
  it('muestra la tarjeta roja con el motivo', async () => {
    const user = userEvent.setup()
    denegado()
    render(<CheckIn />)
    await escanear(user, 'TOKEN')

    expect(await screen.findByText(/acceso denegado/i)).toBeInTheDocument()
    expect(screen.getByText(/membresía no activa/i)).toBeInTheDocument()
  })

  it('token inválido muestra el error del backend', async () => {
    const user = userEvent.setup()
    server.use(http.post('/api/accesos/checkin/', () =>
      HttpResponse.json({ error: 'Token inválido' }, { status: 404 })))
    render(<CheckIn />)
    await escanear(user, 'NO-EXISTE')

    expect(await screen.findByText(/token inválido/i)).toBeInTheDocument()
  })

  it('socio suspendido muestra su motivo', async () => {
    const user = userEvent.setup()
    denegado({ motivo: 'socio suspendido' })
    render(<CheckIn />)
    await escanear(user, 'TOKEN')

    expect(await screen.findByText(/socio suspendido/i)).toBeInTheDocument()
  })

  it('error de red no deja la pantalla en blanco ni el botón trabado', async () => {
    const user = userEvent.setup()
    server.use(http.post('/api/accesos/checkin/', () => HttpResponse.error()))
    render(<CheckIn />)
    await escanear(user, 'TOKEN')

    expect(await screen.findByText(/error de conexión/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /verificar/i })).toBeInTheDocument()
  })

  it('también limpia el input tras un rechazo', async () => {
    const user = userEvent.setup()
    denegado()
    render(<CheckIn />)
    await escanear(user, 'TOKEN')

    await screen.findByText(/acceso denegado/i)
    expect(input()).toHaveValue('')
  })
})

describe('protecciones del kiosco', () => {
  it('no llama a la API con el input vacío', async () => {
    const user = userEvent.setup()
    let llamadas = 0
    server.use(http.post('/api/accesos/checkin/', () => {
      llamadas += 1
      return HttpResponse.json({ acceso: 'permitido', socio: 'x', plan: 'y', vence: null })
    }))
    render(<CheckIn />)
    await user.click(input())
    await user.keyboard('{Enter}')

    expect(llamadas).toBe(0)
  })

  it('el botón está deshabilitado mientras no haya código', async () => {
    render(<CheckIn />)
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /verificar/i })).toBeDisabled()
    })
  })

  it('dos escaneos seguidos muestran el resultado del segundo', async () => {
    const user = userEvent.setup()
    permitido({ socio: 'Ana Lopez' })
    render(<CheckIn />)
    await escanear(user, 'TOKEN-ANA')
    await screen.findByText('Ana Lopez')

    permitido({ socio: 'Luis Diaz' })
    await escanear(user, 'TOKEN-LUIS')
    expect(await screen.findByText('Luis Diaz')).toBeInTheDocument()
  })
})
