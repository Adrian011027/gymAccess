import { useCallback, useEffect, useState } from 'react'
import api from '../api/axios'
import toast from 'react-hot-toast'

const CARD_STYLE = { backgroundColor: '#161b22', border: '1px solid #21262d' }
const INPUT_STYLE = { backgroundColor: '#0d1117', border: '1px solid #21262d', color: '#fff' }

const METODOS = [
  ['efectivo', 'Efectivo'],
  ['tarjeta', 'Tarjeta'],
  ['transferencia', 'Transferencia'],
]

const TIPO = {
  membresia: { label: 'Membresía', color: '#3b82f6' },
  tienda: { label: 'Tienda', color: '#a855f7' },
  gasto: { label: 'Gasto', color: '#ef4444' },
}

const money = n => `$${Number(n || 0).toLocaleString('es-MX', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`

// `toISOString()` da la fecha en UTC: a las 7 de la noche en México ya adelanta un día
// y el corte se abriría en el de mañana, vacío, justo a la hora de cerrar la caja.
function hoyLocal() {
  const d = new Date()
  return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().split('T')[0]
}

function horaDe(iso) {
  if (!iso) return '—'
  return new Date(iso).toLocaleTimeString('es-MX', { hour: '2-digit', minute: '2-digit' })
}

/**
 * Corte de caja de un día: lo cobrado por membresías, lo vendido en tienda y lo que
 * salió en gastos, en una sola pantalla y con el efectivo que debe haber en el cajón.
 *
 * Vive en un componente y no dentro del POS porque la misma cuenta se necesita al
 * cerrar la caja (Punto de Venta) y al revisar el día (Pagos): duplicarla es cómo
 * dos pantallas terminan dando totales distintos del mismo día.
 *
 * `sucursal` solo lo atiende el backend para quien no está atado a una sucursal;
 * a recepción se le ignora y siempre ve su propia caja.
 */
export default function CorteDelDia({ sucursal = '', sucursales = [] }) {
  const [fecha, setFecha] = useState(hoyLocal)
  const [datos, setDatos] = useState(null)
  const [cargando, setCargando] = useState(true)

  const cargar = useCallback(() => {
    setCargando(true)
    const params = new URLSearchParams({ fecha })
    if (sucursal) params.set('sucursal', sucursal)
    return api.get(`/socios/pagos/corte/?${params}`)
      .then(r => setDatos(r.data))
      .catch(err => {
        setDatos(null)
        toast.error(err?.response?.data?.fecha?.[0] || 'No se pudo cargar el corte')
      })
      .finally(() => setCargando(false))
  }, [fecha, sucursal])

  useEffect(() => { cargar() }, [cargar])

  const esHoy = fecha === hoyLocal()
  const nombreSucursal = datos?.sucursal?.nombre
    || sucursales.find(s => String(s.id) === String(sucursal))?.nombre
    || 'Todas las sucursales'

  // Para pasar el corte por WhatsApp al dueño sin teclearlo de nuevo, que es como se
  // reporta el cierre en la práctica.
  const copiar = () => {
    if (!datos) return
    const lineas = [
      `CORTE ${datos.fecha} · ${nombreSucursal}`,
      '',
      `Membresías: ${money(datos.membresias.total)} (${datos.membresias.num})`,
      `Tienda: ${money(datos.tienda.total)} (${datos.tienda.num})`,
      `Cobrado: ${money(datos.ingresos.total)}`,
      `Gastos: -${money(datos.gastos.total)} (${datos.gastos.num})`,
      `Neto del día: ${money(datos.neto)}`,
      '',
      'Cobrado por método:',
      ...METODOS.map(([v, l]) => `  ${l}: ${money(datos.ingresos.por_metodo[v])}`),
      '',
      `Efectivo esperado en caja: ${money(datos.efectivo_esperado)}`,
    ]
    navigator.clipboard?.writeText(lineas.join('\n'))
      .then(() => toast.success('Corte copiado'))
      .catch(() => toast.error('No se pudo copiar'))
  }

  const tarjetas = datos ? [
    { label: 'Cobrado hoy', valor: money(datos.ingresos.total), color: '#22c55e',
      pie: `${datos.ingresos.num} movimiento${datos.ingresos.num === 1 ? '' : 's'}` },
    { label: 'Membresías', valor: money(datos.membresias.total), color: '#3b82f6',
      pie: `${datos.membresias.num} cobro${datos.membresias.num === 1 ? '' : 's'}` },
    { label: 'Tienda', valor: money(datos.tienda.total), color: '#a855f7',
      pie: `${datos.tienda.num} ticket${datos.tienda.num === 1 ? '' : 's'}` },
    { label: 'Gastos', valor: `-${money(datos.gastos.total)}`, color: '#ef4444',
      pie: `${datos.gastos.num} salida${datos.gastos.num === 1 ? '' : 's'}` },
  ] : []

  return (
    <div className="space-y-4">
      {/* Barra de fecha */}
      <div className="flex flex-wrap items-center gap-2">
        <input
          type="date"
          value={fecha}
          max={hoyLocal()}
          onChange={e => setFecha(e.target.value)}
          className="rounded-lg px-3 py-2 text-xs font-semibold focus:outline-none"
          style={INPUT_STYLE}
        />
        {!esHoy && (
          <button
            onClick={() => setFecha(hoyLocal())}
            className="px-3 py-2 rounded-lg text-xs font-semibold"
            style={{ backgroundColor: '#161b22', color: '#8b949e', border: '1px solid #21262d' }}
          >
            Hoy
          </button>
        )}
        <button
          onClick={cargar}
          className="px-3 py-2 rounded-lg text-xs font-semibold"
          style={{ backgroundColor: '#161b22', color: '#8b949e', border: '1px solid #21262d' }}
        >
          Actualizar
        </button>
        <span className="text-[10px] ml-1" style={{ color: '#8b949e' }}>
          Caja de <span className="text-white font-semibold">{nombreSucursal}</span>
        </span>
        <button
          onClick={copiar}
          disabled={!datos}
          className="ml-auto px-3 py-2 rounded-lg text-xs font-bold disabled:opacity-40"
          style={{ backgroundColor: '#22c55e', color: '#0d1117' }}
        >
          Copiar corte
        </button>
      </div>

      {!datos && (
        <div className="rounded-xl py-10 text-center text-xs" style={{ ...CARD_STYLE, color: '#3d444d' }}>
          {cargando
            ? 'Cargando corte...'
            : 'No se pudo cargar el corte. Pulsa Actualizar para reintentar.'}
        </div>
      )}

      {datos && (
        <>
          <div className="grid gap-3 grid-cols-2 lg:grid-cols-4">
            {tarjetas.map(t => (
              <div key={t.label} className="rounded-xl p-4" style={CARD_STYLE}>
                <p className="text-[10px] tracking-widest" style={{ color: '#8b949e' }}>{t.label.toUpperCase()}</p>
                <p className="text-lg font-black mt-1" style={{ color: t.color }}>{t.valor}</p>
                <p className="text-[10px] mt-0.5" style={{ color: '#3d444d' }}>{t.pie}</p>
              </div>
            ))}
          </div>

          <div className="grid gap-3 lg:grid-cols-[1fr_320px]">
            {/* Desglose por método */}
            <div className="rounded-xl p-4" style={CARD_STYLE}>
              <h3 className="text-[10px] font-bold tracking-widest mb-3" style={{ color: '#8b949e' }}>
                CÓMO ENTRÓ EL DINERO
              </h3>
              <div className="overflow-x-auto">
                <table className="w-full text-sm min-w-[420px]">
                  <thead style={{ borderBottom: '1px solid #21262d' }}>
                    <tr>
                      {['MÉTODO', 'MEMBRESÍAS', 'TIENDA', 'GASTOS', 'NETO'].map(h => (
                        <th key={h} className="px-2 py-2 text-left text-[10px] font-bold tracking-widest" style={{ color: '#8b949e' }}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {/* La última columna es el neto (entradas − gastos), no las entradas:
                        con "Total" al lado de un gasto en rojo la fila no cuadraba a la
                        vista y parecía una suma mal hecha. Así el renglón de efectivo da
                        exactamente el efectivo esperado en caja. */}
                    {METODOS.map(([v, l]) => {
                      const gasto = Number(datos.gastos.por_metodo[v]) || 0
                      const neto = (Number(datos.ingresos.por_metodo[v]) || 0) - gasto
                      return (
                        <tr key={v} style={{ borderBottom: '1px solid #21262d' }}>
                          <td className="px-2 py-2 text-xs font-semibold text-white">{l}</td>
                          <td className="px-2 py-2 text-xs" style={{ color: '#8b949e' }}>{money(datos.membresias.por_metodo[v])}</td>
                          <td className="px-2 py-2 text-xs" style={{ color: '#8b949e' }}>{money(datos.tienda.por_metodo[v])}</td>
                          <td className="px-2 py-2 text-xs" style={{ color: gasto ? '#ef4444' : '#3d444d' }}>
                            {gasto ? `-${money(gasto)}` : money(0)}
                          </td>
                          <td className="px-2 py-2 text-xs font-bold" style={{ color: neto < 0 ? '#ef4444' : '#22c55e' }}>
                            {money(neto)}
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Cierre */}
            <div className="rounded-xl p-4 space-y-3 h-fit" style={CARD_STYLE}>
              <h3 className="text-[10px] font-bold tracking-widest" style={{ color: '#8b949e' }}>CIERRE DEL DÍA</h3>
              <div className="flex items-baseline justify-between">
                <span className="text-[11px]" style={{ color: '#8b949e' }}>Cobrado</span>
                <span className="text-sm font-bold text-white">{money(datos.ingresos.total)}</span>
              </div>
              <div className="flex items-baseline justify-between">
                <span className="text-[11px]" style={{ color: '#8b949e' }}>Gastos</span>
                <span className="text-sm font-bold" style={{ color: '#ef4444' }}>-{money(datos.gastos.total)}</span>
              </div>
              <div className="flex items-baseline justify-between pt-2" style={{ borderTop: '1px solid #21262d' }}>
                <span className="text-[11px]" style={{ color: '#8b949e' }}>Neto</span>
                <span className="text-base font-black" style={{ color: Number(datos.neto) < 0 ? '#ef4444' : '#22c55e' }}>
                  {money(datos.neto)}
                </span>
              </div>
              <div className="rounded-lg p-3 mt-1" style={{ backgroundColor: 'rgba(34,197,94,0.08)', border: '1px solid rgba(34,197,94,0.3)' }}>
                <p className="text-[10px] tracking-widest" style={{ color: '#22c55e' }}>EFECTIVO ESPERADO EN CAJA</p>
                <p className="text-xl font-black mt-1" style={{ color: '#22c55e' }}>{money(datos.efectivo_esperado)}</p>
                {/* Sin esta línea el número invita a cuadrar contra el cajón completo
                    y siempre sobra: nadie retira el fondo con el que se abrió. */}
                <p className="text-[10px] mt-1 leading-relaxed" style={{ color: '#8b949e' }}>
                  Solo lo movido hoy en efectivo. No incluye el fondo con el que se abrió la caja.
                </p>
              </div>
            </div>
          </div>

          {/* Movimientos */}
          <div className="rounded-xl overflow-hidden" style={CARD_STYLE}>
            <div className="px-4 py-3" style={{ borderBottom: '1px solid #21262d' }}>
              <h3 className="text-[10px] font-bold tracking-widest" style={{ color: '#8b949e' }}>
                MOVIMIENTOS DEL DÍA ({datos.movimientos.length})
              </h3>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm min-w-[640px]">
                <thead style={{ borderBottom: '1px solid #21262d' }}>
                  <tr>
                    {['HORA', 'TIPO', 'CONCEPTO', 'MÉTODO', 'REGISTRÓ', 'MONTO'].map(h => (
                      <th key={h} className="px-4 py-3 text-left text-[10px] font-bold tracking-widest" style={{ color: '#8b949e' }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {datos.movimientos.map((m, i) => {
                    const t = TIPO[m.tipo] || { label: m.tipo, color: '#8b949e' }
                    return (
                      <tr key={`${m.tipo}-${i}`} style={{ borderBottom: i < datos.movimientos.length - 1 ? '1px solid #21262d' : undefined }}>
                        <td className="px-4 py-3 text-xs" style={{ color: '#8b949e' }}>{horaDe(m.fecha)}</td>
                        <td className="px-4 py-3">
                          <span className="text-[10px] px-2 py-0.5 rounded font-semibold"
                            style={{ backgroundColor: `${t.color}1a`, color: t.color }}>
                            {t.label}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-xs text-white">
                          {m.concepto}
                          {m.referencia && <span className="ml-1" style={{ color: '#3d444d' }}>{m.referencia}</span>}
                        </td>
                        <td className="px-4 py-3 text-xs capitalize" style={{ color: '#8b949e' }}>{m.metodo}</td>
                        <td className="px-4 py-3 text-xs" style={{ color: '#8b949e' }}>{m.registrado_por || '—'}</td>
                        <td className="px-4 py-3 text-xs font-bold" style={{ color: m.signo < 0 ? '#ef4444' : '#22c55e' }}>
                          {m.signo < 0 ? '-' : ''}{money(m.monto)}
                        </td>
                      </tr>
                    )
                  })}
                  {datos.movimientos.length === 0 && (
                    <tr><td colSpan={6} className="px-4 py-10 text-center text-xs" style={{ color: '#3d444d' }}>
                      Sin movimientos {esHoy ? 'todavía hoy' : 'ese día'}
                    </td></tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </div>
  )
}
