import { useEffect, useState } from 'react'
import api from '../api/axios'
import toast from 'react-hot-toast'
import { useAuth } from '../context/AuthContext'

const CARD_STYLE = { backgroundColor: '#161b22', border: '1px solid #21262d' }

const AVATAR_COLORS = ['#f97316', '#a855f7', '#3b82f6', '#22c55e', '#ef4444', '#eab308', '#06b6d4']
function avatarColor(name = '') { return AVATAR_COLORS[(name.charCodeAt(0) || 0) % AVATAR_COLORS.length] }
function initials(name = '') { return name.split(' ').slice(0, 2).map(w => w[0]).join('').toUpperCase() }

export default function Pagos() {
  const { isAdmin } = useAuth()
  const [membresias, setMembresias] = useState([])
  const [tab, setTab] = useState('hoy')
  const [loading, setLoading] = useState(false)

  const load = () => api.get('/socios/membresias/').then(r => setMembresias(r.data)).catch(() => {})
  useEffect(() => { load() }, [])

  const hoy = new Date().toISOString().split('T')[0]
  const semana = new Date(Date.now() + 7 * 86400000).toISOString().split('T')[0]

  const pendientes = membresias.filter(m => m.estado !== 'activa' || m.fecha_fin <= semana)
  const pendHoy    = pendientes.filter(m => m.fecha_fin === hoy || m.estado === 'pendiente_pago')
  const pendSem    = pendientes.filter(m => m.fecha_fin > hoy && m.fecha_fin <= semana)
  const atrasados  = membresias.filter(m => m.fecha_fin < hoy && m.estado !== 'activa')

  const cobrar = async (mem) => {
    setLoading(true)
    try {
      await api.post('/socios/pagos/', { membresia: mem.id, monto: mem.precio || 499, metodo: 'efectivo' })
      toast.success(`Pago registrado — ${mem.socio_nombre}`)
      load()
    } catch {
      toast.error('Error al registrar pago')
    } finally {
      setLoading(false)
    }
  }

  const tabs = [
    { key: 'hoy',       label: `Hoy (${pendHoy.length})` },
    { key: 'semana',    label: `Esta semana (${pendSem.length})` },
    { key: 'atrasados', label: `Atrasados (${atrasados.length})` },
  ]

  const lista = tab === 'hoy' ? pendHoy : tab === 'semana' ? pendSem : atrasados

  const totalCobradoMes = membresias.filter(m => m.estado === 'activa').length * 499

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
              <span className="text-sm font-bold" style={{ color: '#f97316' }}>$499</span>
              <button
                onClick={() => cobrar(m)}
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
              Total pendiente: <span className="font-bold" style={{ color: '#22c55e' }}>${(lista.length * 499).toLocaleString()}</span>
            </p>
          </div>
        )}
      </div>
    </div>
  )
}
