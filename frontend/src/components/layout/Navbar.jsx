import { useLocation } from 'react-router-dom'

const ROUTE_LABELS = {
  '/dashboard':    'Dashboard',
  '/socios':       'Socios',
  '/clases':       'Clases',
  '/equipamiento': 'Equipamiento',
  '/reportes':     'Reportes',
  '/pagos':        'Pagos',
  '/configuracion':'Configuración',
}

function useNow() {
  return new Date().toLocaleDateString('es-MX', {
    weekday: 'long', day: 'numeric', month: 'long', year: 'numeric'
  }).replace(/^\w/, c => c.toUpperCase())
}

export default function Navbar() {
  const location = useLocation()
  const pageLabel = ROUTE_LABELS[location.pathname] || 'GymAccess'
  const dateStr = useNow()

  return (
    <header
      className="h-16 flex items-center justify-between px-6 shrink-0"
      style={{ backgroundColor: '#0d1117', borderBottom: '1px solid #21262d' }}
    >
      {/* Left: page title + date */}
      <div>
        <h1 className="text-sm font-black tracking-widest text-white uppercase">{pageLabel}</h1>
        <p className="text-[10px] mt-0.5 capitalize" style={{ color: '#8b949e' }}>{dateStr}</p>
      </div>

      {/* Right: search + bell + gym status */}
      <div className="flex items-center gap-3">
        {/* Search */}
        <div
          className="flex items-center gap-2 px-3 py-1.5 rounded-lg"
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
        <button className="relative p-2 rounded-lg transition-colors hover:opacity-80" style={{ backgroundColor: '#161b22', border: '1px solid #21262d' }}>
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" style={{ color: '#8b949e' }}>
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
          </svg>
          <span
            className="absolute -top-1 -right-1 w-4 h-4 rounded-full text-[9px] font-bold flex items-center justify-center text-white"
            style={{ backgroundColor: '#f97316' }}
          >
            3
          </span>
        </button>

        {/* Gym status */}
        <div
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold"
          style={{ backgroundColor: '#161b22', border: '1px solid #21262d', color: '#22c55e' }}
        >
          <span className="w-1.5 h-1.5 rounded-full bg-[#22c55e] animate-pulse" />
          Gym Abierto
        </div>
      </div>
    </header>
  )
}
