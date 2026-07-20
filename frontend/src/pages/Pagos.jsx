import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import api from '../api/axios'
import toast from 'react-hot-toast'
import { useAuth } from '../context/AuthContext'

const CARD_STYLE = { backgroundColor: '#161b22', border: '1px solid #21262d' }
const INPUT_STYLE = { backgroundColor: '#0d1117', border: '1px solid #21262d', color: '#fff' }

const AVATAR_COLORS = ['#f97316', '#a855f7', '#3b82f6', '#22c55e', '#ef4444', '#eab308', '#06b6d4']
function avatarColor(name = '') { return AVATAR_COLORS[(name.charCodeAt(0) || 0) % AVATAR_COLORS.length] }
function initials(name = '') { return name.split(' ').slice(0, 2).map(w => w[0]).join('').toUpperCase() }

const METODO_LABEL = { efectivo: 'Efectivo', tarjeta: 'Tarjeta', transferencia: 'Transferencia' }
const CATEGORIAS_GASTO = [
  ['renta', 'Renta'], ['nomina', 'Nómina'], ['equipo', 'Equipo'],
  ['servicios', 'Servicios'], ['mantenimiento', 'Mantenimiento'], ['marketing', 'Marketing'], ['otro', 'Otro'],
]
const GASTO_EMPTY = { categoria: 'otro', descripcion: '', monto: '', fecha: new Date().toISOString().split('T')[0] }

function horaDe(fechaISO) {
  return new Date(fechaISO).toLocaleTimeString('es-MX', { hour: '2-digit', minute: '2-digit' })
}

export default function Pagos() {
  const { isAdmin } = useAuth()
  const [searchParams] = useSearchParams()
  const [vista, setVista] = useState('pendientes') // pendientes | registro | gastos

  const [membresias, setMembresias] = useState([])
  const [tab, setTab] = useState(searchParams.get('tab') || 'hoy')
  const [loading, setLoading] = useState(false)
  const [confirmar, setConfirmar] = useState(null)
  const [monto, setMonto] = useState('')
  const [metodo, setMetodo] = useState('efectivo')

  const [pagos, setPagos] = useState([])
  const [regTab, setRegTab] = useState('hoy')

  const [gastos, setGastos] = useState([])
  const [gastoModal, setGastoModal] = useState(false)
  const [gastoForm, setGastoForm] = useState(GASTO_EMPTY)

  const load = () => api.get('/socios/membresias/').then(r => setMembresias(r.data)).catch(() => {})
  const loadPagos = () => api.get('/socios/pagos/').then(r => setPagos(r.data)).catch(() => {})
  const loadGastos = () => api.get('/socios/gastos/').then(r => setGastos(r.data)).catch(() => {})

  useEffect(() => {
    load()
    loadPagos()
    if (isAdmin) loadGastos()
  }, [isAdmin])

  const hoy = new Date().toISOString().split('T')[0]
  const semana = new Date(Date.now() + 7 * 86400000).toISOString().split('T')[0]

  const pendientes = membresias.filter(m => m.estado !== 'activa' || m.fecha_fin <= semana)
  const pendHoy    = pendientes.filter(m => m.fecha_fin === hoy || m.estado === 'pendiente_pago')
  const pendSem    = pendientes.filter(m => m.fecha_fin > hoy && m.fecha_fin <= semana)
  const atrasados  = membresias.filter(m => m.fecha_fin < hoy && m.estado !== 'activa')

  const abrirConfirmacion = mem => {
    setConfirmar(mem)
    setMonto(String(mem.plan_precio ?? ''))
    setMetodo('efectivo')
  }

  const confirmarPago = async () => {
    if (!confirmar) return
    setLoading(true)
    try {
      await api.post('/socios/pagos/', { membresia: confirmar.id, monto, metodo })
      toast.success(`Pago confirmado — ${confirmar.socio_nombre}`)
      setConfirmar(null)
      load()
      loadPagos()
    } catch {
      toast.error('Error al registrar pago')
    } finally {
      setLoading(false)
    }
  }

  const guardarGasto = async e => {
    e.preventDefault()
    try {
      await api.post('/socios/gastos/', gastoForm)
      toast.success('Gasto registrado')
      setGastoModal(false)
      setGastoForm(GASTO_EMPTY)
      loadGastos()
    } catch {
      toast.error('Error al guardar el gasto')
    }
  }

  const tabs = [
    { key: 'hoy',       label: `Hoy (${pendHoy.length})` },
    { key: 'semana',    label: `Esta semana (${pendSem.length})` },
    { key: 'atrasados', label: `Atrasados (${atrasados.length})` },
  ]

  const lista = tab === 'hoy' ? pendHoy : tab === 'semana' ? pendSem : atrasados

  const totalCobradoMes = membresias
    .filter(m => m.estado === 'activa')
    .reduce((sum, m) => sum + Number(m.plan_precio || 0), 0)

  const inicioSemana = new Date(Date.now() - 7 * 86400000).toISOString().split('T')[0]
  const pagosHoy = pagos.filter(p => p.fecha?.startsWith(hoy))
  const pagosSemana = pagos.filter(p => p.fecha?.split('T')[0] >= inicioSemana)
  const listaRegistro = (regTab === 'hoy' ? pagosHoy : pagosSemana)
    .slice()
    .sort((a, b) => new Date(b.fecha) - new Date(a.fecha))
  const totalRegistro = listaRegistro.reduce((sum, p) => sum + Number(p.monto || 0), 0)

  const totalGastos = gastos.reduce((sum, g) => sum + Number(g.monto || 0), 0)

  const VISTAS = [
    ['pendientes', 'Por cobrar'],
    ['registro', 'Registro de pagos'],
    ...(isAdmin ? [['gastos', 'Gastos']] : []),
  ]

  return (
    <div className="space-y-5">
      <h2 className="text-xl font-black text-white uppercase tracking-wide">PAGOS</h2>

      {/* Stat cards — el total cobrado solo lo ve el admin */}
      <div className={`grid grid-cols-2 gap-4 ${isAdmin ? 'lg:grid-cols-4' : 'lg:grid-cols-3'}`}>
        {[
          { icon: '⏱', label: 'Pendientes hoy', value: pendHoy.length, color: '#f97316' },
          { icon: '📅', label: 'Esta semana', value: pendSem.length, color: '#3b82f6' },
          { icon: '⚠', label: 'Atrasados', value: atrasados.length, color: '#ef4444' },
          ...(isAdmin ? [{ icon: '✓', label: 'Cobrado este mes', value: `$${totalCobradoMes.toLocaleString()}`, color: '#22c55e' }] : []),
        ].map(s => (
          <div key={s.label} className="rounded-xl p-4 flex items-center gap-3" style={CARD_STYLE}>
            <div className="w-9 h-9 rounded-full flex items-center justify-center text-sm shrink-0"
              style={{ backgroundColor: s.color + '20', color: s.color }}>
              {s.icon}
            </div>
            <div>
              <p className="text-lg font-black text-white">{s.value}</p>
              <p className="text-[10px]" style={{ color: '#8b949e' }}>{s.label}</p>
            </div>
          </div>
        ))}
      </div>

      {/* Vistas */}
      <div className="flex gap-1 flex-wrap">
        {VISTAS.map(([v, l]) => (
          <button
            key={v}
            onClick={() => setVista(v)}
            className="px-4 py-2 rounded-lg text-xs font-bold transition-all"
            style={vista === v
              ? { backgroundColor: '#3b82f6', color: '#fff' }
              : { backgroundColor: '#161b22', color: '#8b949e', border: '1px solid #21262d' }
            }
          >{l}</button>
        ))}
      </div>

      {vista === 'pendientes' && (
        <>
          {/* Tabs */}
          <div className="flex gap-1 flex-wrap">
            {tabs.map(t => (
              <button
                key={t.key}
                onClick={() => setTab(t.key)}
                className="px-4 py-2 rounded-lg text-xs font-semibold transition-all"
                style={tab === t.key
                  ? { backgroundColor: '#22c55e', color: '#0d1117' }
                  : { backgroundColor: '#161b22', color: '#8b949e', border: '1px solid #21262d' }
                }
              >{t.label}</button>
            ))}
          </div>

          {/* Lista */}
          <div className="rounded-xl p-5 space-y-3" style={CARD_STYLE}>
            {lista.length === 0 && (
              <p className="text-center text-xs py-8" style={{ color: '#3d444d' }}>Sin pagos en este período</p>
            )}
            {lista.map(m => (
              <div key={m.id} className="flex items-center justify-between gap-3 flex-wrap py-3" style={{ borderBottom: '1px solid #21262d' }}>
                <div className="flex items-center gap-3">
                  <div className="w-9 h-9 rounded-full flex items-center justify-center text-[11px] font-bold shrink-0"
                    style={{ backgroundColor: avatarColor(m.socio_nombre), color: '#0d1117' }}>
                    {initials(m.socio_nombre)}
                  </div>
                  <div>
                    <p className="text-sm font-semibold text-white">{m.socio_nombre}</p>
                    <p className="text-[10px]" style={{ color: '#8b949e' }}>{m.plan_nombre} · Vence: {m.fecha_fin}</p>
                  </div>
                </div>
                <div className="flex items-center gap-4">
                  <span className="text-sm font-bold" style={{ color: '#f97316' }}>${m.plan_precio ?? '—'}</span>
                  <button
                    onClick={() => abrirConfirmacion(m)}
                    disabled={loading}
                    className="px-4 py-2 rounded-lg text-xs font-bold transition-all disabled:opacity-50"
                    style={{ backgroundColor: '#22c55e', color: '#0d1117' }}
                    onMouseEnter={e => { if (!loading) e.currentTarget.style.backgroundColor = '#16a34a' }}
                    onMouseLeave={e => { if (!loading) e.currentTarget.style.backgroundColor = '#22c55e' }}
                  >
                    Cobrar
                  </button>
                </div>
              </div>
            ))}
            {lista.length > 0 && (
              <div className="pt-2">
                <p className="text-xs" style={{ color: '#8b949e' }}>
                  Total pendiente: <span className="font-bold" style={{ color: '#22c55e' }}>
                    ${lista.reduce((sum, m) => sum + Number(m.plan_precio || 0), 0).toLocaleString()}
                  </span>
                </p>
              </div>
            )}
          </div>
        </>
      )}

      {vista === 'registro' && (
        <>
          <div className="flex gap-1 flex-wrap">
            {[['hoy', `Hoy (${pagosHoy.length})`], ['semana', `Esta semana (${pagosSemana.length})`]].map(([v, l]) => (
              <button
                key={v}
                onClick={() => setRegTab(v)}
                className="px-4 py-2 rounded-lg text-xs font-semibold transition-all"
                style={regTab === v
                  ? { backgroundColor: '#22c55e', color: '#0d1117' }
                  : { backgroundColor: '#161b22', color: '#8b949e', border: '1px solid #21262d' }
                }
              >{l}</button>
            ))}
          </div>

          <div className="rounded-xl overflow-hidden" style={CARD_STYLE}>
            <div className="overflow-x-auto">
              <table className="w-full text-sm min-w-[640px]">
                <thead style={{ borderBottom: '1px solid #21262d' }}>
                  <tr>
                    {['SOCIO', 'PLAN', 'HORA', 'MÉTODO', 'MONTO'].map(h => (
                      <th key={h} className="px-4 py-3 text-left text-[10px] font-bold tracking-widest" style={{ color: '#8b949e' }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {listaRegistro.map((p, i) => (
                    <tr key={p.id} style={{ borderBottom: i < listaRegistro.length - 1 ? '1px solid #21262d' : undefined }}>
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-2.5">
                          <div className="w-7 h-7 rounded-full flex items-center justify-center text-[10px] font-bold shrink-0"
                            style={{ backgroundColor: avatarColor(p.socio_nombre), color: '#0d1117' }}>
                            {initials(p.socio_nombre)}
                          </div>
                          <span className="text-xs font-semibold text-white">{p.socio_nombre}</span>
                        </div>
                      </td>
                      <td className="px-4 py-3 text-xs" style={{ color: '#8b949e' }}>{p.plan_nombre}</td>
                      <td className="px-4 py-3 text-xs" style={{ color: '#8b949e' }}>
                        {new Date(p.fecha).toLocaleDateString('es-MX', { day: 'numeric', month: 'short' })} · {horaDe(p.fecha)}
                      </td>
                      <td className="px-4 py-3">
                        <span className="text-[10px] px-2 py-0.5 rounded font-semibold" style={{ backgroundColor: 'rgba(59,130,246,0.15)', color: '#3b82f6' }}>
                          {METODO_LABEL[p.metodo] || p.metodo}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-sm font-bold" style={{ color: '#22c55e' }}>${Number(p.monto).toLocaleString()}</td>
                    </tr>
                  ))}
                  {listaRegistro.length === 0 && (
                    <tr><td colSpan={5} className="px-4 py-10 text-center text-xs" style={{ color: '#3d444d' }}>Sin pagos registrados en este período</td></tr>
                  )}
                </tbody>
              </table>
            </div>
            {listaRegistro.length > 0 && (
              <div className="px-4 py-3" style={{ borderTop: '1px solid #21262d' }}>
                <p className="text-xs" style={{ color: '#8b949e' }}>
                  Total del período: <span className="font-bold" style={{ color: '#22c55e' }}>${totalRegistro.toLocaleString()}</span>
                  <span className="ml-2">({listaRegistro.length} pago{listaRegistro.length !== 1 ? 's' : ''})</span>
                </p>
              </div>
            )}
          </div>
        </>
      )}

      {vista === 'gastos' && isAdmin && (
        <>
          <div className="flex items-center justify-between gap-3 flex-wrap">
            <p className="text-xs" style={{ color: '#8b949e' }}>
              Total registrado: <span className="font-bold" style={{ color: '#ef4444' }}>${totalGastos.toLocaleString()}</span>
            </p>
            <button
              onClick={() => { setGastoForm(GASTO_EMPTY); setGastoModal(true) }}
              className="px-4 py-2 rounded-lg text-xs font-bold"
              style={{ backgroundColor: '#22c55e', color: '#0d1117' }}
            >
              + Registrar gasto
            </button>
          </div>

          <div className="rounded-xl overflow-hidden" style={CARD_STYLE}>
            <div className="overflow-x-auto">
              <table className="w-full text-sm min-w-[560px]">
                <thead style={{ borderBottom: '1px solid #21262d' }}>
                  <tr>
                    {['CATEGORÍA', 'DESCRIPCIÓN', 'MONTO', 'FECHA'].map(h => (
                      <th key={h} className="px-4 py-3 text-left text-[10px] font-bold tracking-widest" style={{ color: '#8b949e' }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {gastos.map((g, i) => (
                    <tr key={g.id} style={{ borderBottom: i < gastos.length - 1 ? '1px solid #21262d' : undefined }}>
                      <td className="px-4 py-3 text-xs capitalize" style={{ color: '#fff' }}>{g.categoria}</td>
                      <td className="px-4 py-3 text-xs" style={{ color: '#8b949e' }}>{g.descripcion}</td>
                      <td className="px-4 py-3 text-sm font-bold" style={{ color: '#ef4444' }}>${Number(g.monto).toLocaleString()}</td>
                      <td className="px-4 py-3 text-xs" style={{ color: '#8b949e' }}>{g.fecha}</td>
                    </tr>
                  ))}
                  {gastos.length === 0 && (
                    <tr><td colSpan={4} className="px-4 py-10 text-center text-xs" style={{ color: '#3d444d' }}>Sin gastos registrados</td></tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}

      {confirmar && (
        <div className="fixed inset-0 flex items-center justify-center z-50 p-4" style={{ backgroundColor: 'rgba(0,0,0,0.7)' }}>
          <div className="rounded-2xl p-6 w-full max-w-sm" style={CARD_STYLE}>
            <h2 className="text-sm font-bold text-white mb-1">Confirmar pago</h2>
            <p className="text-xs mb-5" style={{ color: '#8b949e' }}>
              {confirmar.socio_nombre} · {confirmar.plan_nombre}
            </p>

            <div className="space-y-3">
              <div>
                <label className="text-[10px] font-bold tracking-widest" style={{ color: '#8b949e' }}>MONTO COBRADO</label>
                <div className="flex items-center gap-2 px-3 py-2.5 rounded-lg mt-1" style={{ backgroundColor: '#0d1117', border: '1px solid #21262d' }}>
                  <span className="text-sm" style={{ color: '#8b949e' }}>$</span>
                  <input
                    type="number" step="0.01" value={monto}
                    onChange={e => setMonto(e.target.value)}
                    className="bg-transparent text-white text-sm w-full outline-none"
                  />
                </div>
              </div>
              <div>
                <label className="text-[10px] font-bold tracking-widest" style={{ color: '#8b949e' }}>MÉTODO DE PAGO</label>
                <div className="flex gap-2 mt-1">
                  {[['efectivo', 'Efectivo'], ['tarjeta', 'Tarjeta'], ['transferencia', 'Transferencia']].map(([v, l]) => (
                    <button
                      key={v}
                      type="button"
                      onClick={() => setMetodo(v)}
                      className="flex-1 py-2 rounded-lg text-[11px] font-semibold transition-all"
                      style={metodo === v
                        ? { backgroundColor: '#22c55e', color: '#0d1117' }
                        : { backgroundColor: '#0d1117', color: '#8b949e', border: '1px solid #21262d' }
                      }
                    >{l}</button>
                  ))}
                </div>
              </div>
              <p className="text-[10px] pt-1" style={{ color: '#3d444d' }}>
                Al confirmar, la membresía se reactiva y el socio deja de aparecer como moroso.
              </p>
            </div>

            <div className="flex gap-3 pt-5">
              <button onClick={() => setConfirmar(null)}
                className="flex-1 py-2.5 rounded-lg text-xs font-semibold transition-colors"
                style={{ border: '1px solid #21262d', color: '#8b949e', backgroundColor: 'transparent' }}>
                Cancelar
              </button>
              <button onClick={confirmarPago} disabled={loading || !monto}
                className="flex-1 py-2.5 rounded-lg text-xs font-bold transition-all disabled:opacity-50"
                style={{ backgroundColor: '#22c55e', color: '#0d1117' }}>
                {loading ? 'Confirmando...' : 'Confirmar pago'}
              </button>
            </div>
          </div>
        </div>
      )}

      {gastoModal && (
        <div className="fixed inset-0 flex items-center justify-center z-50 p-4" style={{ backgroundColor: 'rgba(0,0,0,0.7)' }}>
          <div className="rounded-2xl p-6 w-full max-w-sm" style={CARD_STYLE}>
            <h2 className="text-sm font-bold text-white mb-5">Registrar gasto</h2>
            <form onSubmit={guardarGasto} className="space-y-3">
              <div>
                <label className="text-[10px] font-bold tracking-widest" style={{ color: '#8b949e' }}>CATEGORÍA</label>
                <select value={gastoForm.categoria} onChange={e => setGastoForm(f => ({ ...f, categoria: e.target.value }))}
                  className="w-full rounded-lg px-3 py-2 text-sm mt-1 outline-none text-white" style={INPUT_STYLE}>
                  {CATEGORIAS_GASTO.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
                </select>
              </div>
              <div>
                <label className="text-[10px] font-bold tracking-widest" style={{ color: '#8b949e' }}>DESCRIPCIÓN</label>
                <input required value={gastoForm.descripcion} onChange={e => setGastoForm(f => ({ ...f, descripcion: e.target.value }))}
                  className="w-full rounded-lg px-3 py-2 text-sm mt-1 outline-none text-white" style={INPUT_STYLE} />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-[10px] font-bold tracking-widest" style={{ color: '#8b949e' }}>MONTO</label>
                  <input required type="number" step="0.01" value={gastoForm.monto} onChange={e => setGastoForm(f => ({ ...f, monto: e.target.value }))}
                    className="w-full rounded-lg px-3 py-2 text-sm mt-1 outline-none text-white" style={INPUT_STYLE} />
                </div>
                <div>
                  <label className="text-[10px] font-bold tracking-widest" style={{ color: '#8b949e' }}>FECHA</label>
                  <input required type="date" value={gastoForm.fecha} onChange={e => setGastoForm(f => ({ ...f, fecha: e.target.value }))}
                    className="w-full rounded-lg px-3 py-2 text-sm mt-1 outline-none text-white" style={INPUT_STYLE} />
                </div>
              </div>
              <div className="flex gap-3 pt-2">
                <button type="button" onClick={() => setGastoModal(false)}
                  className="flex-1 py-2.5 rounded-lg text-xs font-semibold transition-colors"
                  style={{ border: '1px solid #21262d', color: '#8b949e', backgroundColor: 'transparent' }}>
                  Cancelar
                </button>
                <button type="submit"
                  className="flex-1 py-2.5 rounded-lg text-xs font-bold transition-all"
                  style={{ backgroundColor: '#22c55e', color: '#0d1117' }}>
                  Guardar
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
