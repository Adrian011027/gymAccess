import { useEffect, useRef, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import api from '../../api/axios'

const ROUTE_LABELS = {
  '/checkin':      'Check-In',
  '/dashboard':    'Dashboard',
  '/socios':       'Socios',
  '/clases':       'Clases',
  '/equipamiento': 'Equipamiento',
  '/reportes':     'Reportes',
  '/pagos':        'Pagos',
  '/configuracion':'Configuración',
}

const TIPO_ICONO = {
  pago_vencido: { icon: '⚠', color: '#ef4444' },
  inventario: { icon: '📦', color: '#3b82f6' },
  membresia_por_vencer: { icon: '⏳', color: '#f97316' },
  socio_nuevo: { icon: '👤', color: '#22c55e' },
  otro: { icon: '🔔', color: '#8b949e' },
}

function useNow() {
  return new Date().toLocaleDateString('es-MX', {
    weekday: 'long', day: 'numeric', month: 'long', year: 'numeric'
  }).replace(/^\w/, c => c.toUpperCase())
}

function tiempoDesde(fecha) {
  const diff = (Date.now() - new Date(fecha).getTime()) / 1000
  if (diff < 60) return 'ahora'
  if (diff < 3600) return `hace ${Math.floor(diff / 60)}m`
  if (diff < 86400) return `hace ${Math.floor(diff / 3600)}h`
  return `hace ${Math.floor(diff / 86400)}d`
}

export default function Navbar({ onMenuClick }) {
  const location = useLocation()
  const navigate = useNavigate()
  const pageLabel = ROUTE_LABELS[location.pathname] || 'GymAccess'
  const dateStr = useNow()

  const [notis, setNotis] = useState([])
  const [abierto, setAbierto] = useState(false)
  const ref = useRef(null)

  const cargar = () => api.get('/notificaciones/').then(r => setNotis(r.data)).catch(() => {})

  useEffect(() => {
    cargar()
    const id = setInterval(cargar, 30000)
    return () => clearInterval(id)
  }, [])

  useEffect(() => {
    const onClick = e => { if (ref.current && !ref.current.contains(e.target)) setAbierto(false) }
    document.addEventListener('mousedown', onClick)
    return () => document.removeEventListener('mousedown', onClick)
  }, [])

  const noLeidas = notis.filter(n => !n.leida).length

  const marcarTodas = async () => {
    try {
      await api.post('/notificaciones/marcar-todas-leidas/')
      setNotis(ns => ns.map(n => ({ ...n, leida: true })))
    } catch {}
  }

  const limpiar = async () => {
    try {
      await api.post('/notificaciones/limpiar/')
      setNotis([])
    } catch {}
  }

  const clickNotificacion = async n => {
    if (!n.leida) {
      api.patch(`/notificaciones/${n.id}/`, { leida: true }).catch(() => {})
      setNotis(ns => ns.map(x => x.id === n.id ? { ...x, leida: true } : x))
    }
    setAbierto(false)
    if (n.link) navigate(n.link)
  }

  return (
    <header
      className="h-16 flex items-center justify-between px-4 sm:px-6 shrink-0 gap-3"
      style={{ backgroundColor: '#0d1117', borderBottom: '1px solid #21262d' }}
    >
      {/* Left: menu (móvil) + page title + date */}
      <div className="flex items-center gap-3 min-w-0">
        <button
          onClick={onMenuClick}
          className="lg:hidden p-2 rounded-lg shrink-0"
          style={{ backgroundColor: '#161b22', border: '1px solid #21262d', color: '#8b949e' }}
          aria-label="Abrir menú"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
          </svg>
        </button>
        <div className="min-w-0">
          <h1 className="text-sm font-black tracking-widest text-white uppercase truncate">{pageLabel}</h1>
          <p className="text-[10px] mt-0.5 capitalize truncate" style={{ color: '#8b949e' }}>{dateStr}</p>
        </div>
      </div>

      {/* Right: search + bell + gym status */}
      <div className="flex items-center gap-2 sm:gap-3 shrink-0">
        {/* Search */}
        <div
          className="hidden md:flex items-center gap-2 px-3 py-1.5 rounded-lg"
          style={{ backgroundColor: '#161b22', border: '1px solid #21262d' }}
        >
          <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24" style={{ color: '#8b949e' }}>
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
          <input
            type="text"
            placeholder="Buscar..."
            className="bg-transparent text-sm w-28 outline-none placeholder:text-[#3d444d]"
            style={{ color: '#8b949e' }}
          />
        </div>

        {/* Bell */}
        <div className="relative" ref={ref}>
          <button
            onClick={() => setAbierto(v => !v)}
            className="relative p-2 rounded-lg transition-colors hover:opacity-80"
            style={{ backgroundColor: '#161b22', border: '1px solid #21262d' }}
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" style={{ color: '#8b949e' }}>
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
            </svg>
            {noLeidas > 0 && (
              <span
                className="absolute -top-1 -right-1 min-w-[16px] h-4 px-0.5 rounded-full text-[9px] font-bold flex items-center justify-center text-white"
                style={{ backgroundColor: '#f97316' }}
              >
                {noLeidas > 9 ? '9+' : noLeidas}
              </span>
            )}
          </button>

          {abierto && (
            <div
              className="absolute right-0 mt-2 w-80 max-w-[90vw] rounded-xl overflow-hidden shadow-2xl z-50"
              style={{ backgroundColor: '#161b22', border: '1px solid #21262d' }}
            >
              <div className="flex items-center justify-between px-4 py-3 gap-2" style={{ borderBottom: '1px solid #21262d' }}>
                <span className="text-xs font-bold text-white shrink-0">Notificaciones</span>
                <div className="flex items-center gap-3">
                  {noLeidas > 0 && (
                    <button onClick={marcarTodas} className="text-[10px] font-semibold hover:opacity-80 whitespace-nowrap" style={{ color: '#22c55e' }}>
                      Marcar leídas
                    </button>
                  )}
                  {notis.length > 0 && (
                    <button onClick={limpiar} className="text-[10px] font-semibold hover:opacity-80 whitespace-nowrap" style={{ color: '#8b949e' }}>
                      Limpiar
                    </button>
                  )}
                </div>
              </div>
              <div className="max-h-96 overflow-y-auto">
                {notis.length === 0 && (
                  <p className="text-xs text-center py-8" style={{ color: '#3d444d' }}>Sin notificaciones</p>
                )}
                {notis.map(n => {
                  const cfg = TIPO_ICONO[n.tipo] || TIPO_ICONO.otro
                  return (
                    <button
                      key={n.id}
                      onClick={() => clickNotificacion(n)}
                      className="w-full flex items-start gap-2.5 px-4 py-3 text-left hover:bg-white/5 transition-colors"
                      style={{ borderBottom: '1px solid #21262d', backgroundColor: n.leida ? 'transparent' : 'rgba(34,197,94,0.04)' }}
                    >
                      <span className="text-sm shrink-0" style={{ color: cfg.color }}>{cfg.icon}</span>
                      <div className="min-w-0 flex-1">
                        <p className="text-xs leading-snug" style={{ color: n.leida ? '#8b949e' : '#fff' }}>{n.mensaje}</p>
                        <p className="text-[10px] mt-0.5" style={{ color: '#3d444d' }}>{tiempoDesde(n.creado_en)}</p>
                      </div>
                      {!n.leida && <span className="w-1.5 h-1.5 rounded-full mt-1 shrink-0" style={{ backgroundColor: '#22c55e' }} />}
                    </button>
                  )
                })}
              </div>
              <button
                onClick={() => { setAbierto(false); navigate('/notificaciones') }}
                className="w-full text-center text-[10px] font-semibold py-2.5 hover:opacity-80"
                style={{ color: '#3b82f6', borderTop: '1px solid #21262d' }}
              >
                Ver historial (15 días)
              </button>
            </div>
          )}
        </div>

        {/* Gym status */}
        <div
          className="flex items-center gap-1.5 px-2.5 sm:px-3 py-1.5 rounded-lg text-xs font-semibold"
          style={{ backgroundColor: '#161b22', border: '1px solid #21262d', color: '#22c55e' }}
        >
          <span className="w-1.5 h-1.5 rounded-full bg-[#22c55e] animate-pulse" />
          <span className="hidden sm:inline">Gym Abierto</span>
        </div>
      </div>
    </header>
  )
}
