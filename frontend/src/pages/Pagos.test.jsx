/**
 * La caja. Aquí se cobra, así que los errores cuestan dinero real: un total mal sumado
 * descuadra el corte, y una membresía que no sale de "Atrasados" después de cobrarle
 * hace que se le cobre dos veces al socio.
 */
import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'
import Pagos from './Pagos'
import { server } from '../test/server'
import { renderConSesion } from '../test/utils'

const HOY = new Date().toISOString().split('T')[0]
const AYER = new Date(Date.now() - 86400000).toISOString().split('T')[0]
const EN_3_DIAS = new Date(Date.now() + 3 * 86400000).toISOString().split('T')[0]
const INICIO_MES = HOY.slice(0, 8) + '01'

const MEMBRESIAS = [
  {
    id: 1, socio_nombre: 'Ana Lopez', plan_nombre: 'Mensual', plan_precio: '500.00',
    fecha_fin: AYER, estado: 'vencida',
  },
  {
    id: 2, socio_nombre: 'Luis Diaz', plan_nombre: 'Mensual', plan_precio: '500.00',
    fecha_fin: EN_3_DIAS, estado: 'activa',
  },
  {
    id: 3, socio_nombre: 'Sara Ruiz', plan_nombre: 'Anual', plan_precio: '4800.00',
    fecha_fin: '2027-12-31', estado: 'activa',
  },
]

function datos({ membresias = MEMBRESIAS, pagos = [], gastos = [] } = {}) {
  server.use(
    http.get('/api/socios/membresias/', () => HttpResponse.json(membresias)),
    http.get('/api/socios/pagos/', () => HttpResponse.json(pagos)),
    http.get('/api/socios/gastos/', () => HttpResponse.json(gastos)),
  )
}

const montar = (rol = 'admin') => renderConSesion(<Pagos />, { rol, ruta: '/pagos' })

describe('pestañas de cobranza', () => {
  it('"Atrasados" lista las membresías con fecha ya pasada', async () => {
    datos()
    const user = userEvent.setup()
    montar()
    await user.click(await screen.findByRole('button', { name: /atrasados/i }))

    expect(await screen.findByText('Ana Lopez')).toBeInTheDocument()
    expect(screen.queryByText('Sara Ruiz')).not.toBeInTheDocument()
  })

  it('cuenta correctamente los atrasados en la pestaña', async () => {
    datos()
    montar()
    expect(await screen.findByRole('button', { name: /atrasados \(1\)/i })).toBeInTheDocument()
  })

  it('una membresía vigente y lejana no aparece como pendiente', async () => {
    datos()
    montar()
    await screen.findByRole('button', { name: /atrasados/i })
    expect(screen.queryByText('Sara Ruiz')).not.toBeInTheDocument()
  })

  it('gym sin membresías muestra ceros, no NaN', async () => {
    datos({ membresias: [] })
    montar()
    expect(await screen.findByRole('button', { name: /atrasados \(0\)/i })).toBeInTheDocument()
    expect(screen.queryByText(/NaN/)).not.toBeInTheDocument()
  })
})

describe('cobrar', () => {
  it('el modal precarga el precio del plan, no un monto fijo', async () => {
    datos()
    const user = userEvent.setup()
    montar()
    await user.click(await screen.findByRole('button', { name: /atrasados/i }))
    await user.click(await screen.findByRole('button', { name: /^cobrar$/i }))

    await waitFor(() => {
      expect(screen.getByDisplayValue('500.00')).toBeInTheDocument()
    })
  })

  it('manda la membresía, el monto y el método al backend', async () => {
    let recibido
    datos()
    server.use(http.post('/api/socios/pagos/', async ({ request }) => {
      recibido = await request.json()
      return HttpResponse.json({ id: 9, ...recibido }, { status: 201 })
    }))
    const user = userEvent.setup()
    montar()
    await user.click(await screen.findByRole('button', { name: /atrasados/i }))
    await user.click(await screen.findByRole('button', { name: /^cobrar$/i }))
    await screen.findByDisplayValue('500.00')
    await user.click(screen.getByRole('button', { name: /confirmar/i }))

    await waitFor(() => {
      expect(recibido).toMatchObject({ membresia: 1, monto: '500.00', metodo: 'efectivo' })
    })
  })

  it('permite editar el monto antes de confirmar (pago parcial)', async () => {
    let recibido
    datos()
    server.use(http.post('/api/socios/pagos/', async ({ request }) => {
      recibido = await request.json()
      return HttpResponse.json({ id: 9 }, { status: 201 })
    }))
    const user = userEvent.setup()
    montar()
    await user.click(await screen.findByRole('button', { name: /atrasados/i }))
    await user.click(await screen.findByRole('button', { name: /^cobrar$/i }))

    const campo = await screen.findByDisplayValue('500.00')
    await user.clear(campo)
    await user.type(campo, '250')
    await user.click(screen.getByRole('button', { name: /confirmar/i }))

    await waitFor(() => expect(recibido?.monto).toBe('250'))
  })

  it('tras cobrar, la membresía sale de Atrasados', async () => {
    const user = userEvent.setup()
    datos()
    server.use(http.post('/api/socios/pagos/', () => {
      // El backend renovó: al recargar, Ana ya no está vencida.
      server.use(http.get('/api/socios/membresias/', () => HttpResponse.json(
        MEMBRESIAS.map(m => m.id === 1 ? { ...m, fecha_fin: EN_3_DIAS, estado: 'activa' } : m),
      )))
      return HttpResponse.json({ id: 9 }, { status: 201 })
    }))
    montar()
    await user.click(await screen.findByRole('button', { name: /atrasados/i }))
    await user.click(await screen.findByRole('button', { name: /^cobrar$/i }))
    await screen.findByDisplayValue('500.00')
    await user.click(screen.getByRole('button', { name: /confirmar/i }))

    await waitFor(() => {
      expect(screen.queryByText('Ana Lopez')).not.toBeInTheDocument()
    })
  })

  it('si el cobro falla, el modal sigue abierto y no se pierde el monto', async () => {
    datos()
    server.use(http.post('/api/socios/pagos/', () =>
      HttpResponse.json({ error: 'nel' }, { status: 400 })))
    const user = userEvent.setup()
    montar()
    await user.click(await screen.findByRole('button', { name: /atrasados/i }))
    await user.click(await screen.findByRole('button', { name: /^cobrar$/i }))
    await screen.findByDisplayValue('500.00')
    await user.click(screen.getByRole('button', { name: /confirmar/i }))

    await waitFor(() => {
      expect(screen.getByDisplayValue('500.00')).toBeInTheDocument()
    })
  })
})

describe('"Cobrado este mes" cuenta dinero real', () => {
  const tile = async () => {
    const label = await screen.findByText(/cobrado este mes/i)
    return within(label.closest('div').parentElement).getByText(/^\$/)
  }

  it('suma los pagos del mes, no el precio de las membresías activas', async () => {
    datos({
      pagos: [
        { id: 1, monto: '500.00', fecha: `${HOY}T10:00:00Z` },
        { id: 2, monto: '300.00', fecha: `${INICIO_MES}T10:00:00Z` },
      ],
    })
    montar()
    // Las membresías activas suman 5300; lo cobrado de verdad son 800.
    expect(await tile()).toHaveTextContent('800')
  })

  it('sin pagos registrados el total es cero, aunque haya membresías activas', async () => {
    datos({ pagos: [] })
    montar()
    expect(await tile()).toHaveTextContent('$0')
  })

  it('no cuenta pagos de meses anteriores', async () => {
    datos({
      pagos: [
        { id: 1, monto: '500.00', fecha: `${HOY}T10:00:00Z` },
        { id: 2, monto: '9999.00', fecha: '2020-01-15T10:00:00Z' },
      ],
    })
    montar()
    expect(await tile()).toHaveTextContent('500')
  })
})

describe('el coach y recepción frente a la caja', () => {
  it('recepción no ve la pestaña de Gastos', async () => {
    datos()
    montar('recepcion')
    await screen.findByRole('button', { name: /por cobrar/i })
    expect(screen.queryByRole('button', { name: /^gastos$/i })).not.toBeInTheDocument()
  })

  it('recepción no ve el tile de "Cobrado este mes"', async () => {
    datos()
    montar('recepcion')
    await screen.findByRole('button', { name: /por cobrar/i })
    expect(screen.queryByText(/cobrado este mes/i)).not.toBeInTheDocument()
  })

  it('recepción no pide los gastos: evita un 403 en consola', async () => {
    let pidioGastos = false
    datos()
    server.use(http.get('/api/socios/gastos/', () => {
      pidioGastos = true
      return HttpResponse.json([])
    }))
    montar('recepcion')
    await screen.findByRole('button', { name: /por cobrar/i })
    expect(pidioGastos).toBe(false)
  })

  it('el admin sí ve Gastos', async () => {
    datos()
    montar('admin')
    expect(await screen.findByRole('button', { name: /^gastos$/i })).toBeInTheDocument()
  })
})
