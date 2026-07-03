import { NavLink } from 'react-router-dom'
import { useAuth } from '../../context/AuthContext'

const links = [
  {
    to: '/dashboard', label: 'Dashboard',
    icon: <svg className="w-4 h-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z" /></svg>
  },
  {
    to: '/socios', label: 'Socios',
    icon: <svg className="w-4 h-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" /></svg>
  },
  {
    to: '/clases', label: 'Clases',
    icon: <svg className="w-4 h-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" /></svg>
  },
  {
    to: '/equipamiento', label: 'Equipamiento',
    icon: <svg className="w-4 h-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" /></svg>
  },
  {
    to: '/reportes', label: 'Reportes',
    icon: <svg className="w-4 h-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 12l3-3 3 3 4-4M8 21l4-4 4 4M3 4h18M4 4h16v12a1 1 0 01-1 1H5a1 1 0 01-1-1V4z" /></svg>
  },
  {
    to: '/pagos', label: 'Pagos',
    icon: <svg className="w-4 h-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 10h18M7 15h1m4 0h1m-7 4h12a3 3 0 003-3V8a3 3 0 00-3-3H6a3 3 0 00-3 3v8a3 3 0 003 3z" /></svg>
  },
  {
    to: '/configuracion', label: 'Configuración',
    icon: <svg className="w-4 h-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" /><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" /></svg>
  },
]

function getInitials(name = '') {
  return name.split(' ').slice(0, 2).map(w => w[0]).join('').toUpperCase() || 'JA'
}

export default function Sidebar({ colapsado, setColapsado }) {
  const { user, logout } = useAuth()
  const userName = user?.nombre || user?.username || 'Usuario'

  return (
    <aside
      className="h-screen flex flex-col justify-between relative transition-all duration-300 shrink-0"
      style={{
        backgroundColor: '#0d1117',
        borderRight: '1px solid #21262d',
        width: colapsado ? '64px' : '240px',
      }}
    >
      <div className="overflow-hidden">
        {/* Logo */}
        <div className="p-5 flex items-center gap-3 overflow-hidden whitespace-nowrap" style={{ borderBottom: '1px solid #21262d' }}>
          <div
            className="w-9 h-9 rounded-full flex items-center justify-center shrink-0"
            style={{ backgroundColor: '#161b22', border: '1.5px solid #22c55e' }}
          >
            <svg className="w-5 h-5 text-[#22c55e]" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          </div>
          {!colapsado && (
            <div>
              <h2 className="text-xs font-black tracking-widest" style={{ color: '#22c55e' }}>ROUND3BOXING</h2>
              <p className="text-[9px] font-semibold tracking-widest" style={{ color: '#8b949e' }}>GYM SYSTEM</p>
            </div>
          )}
        </div>

        {/* Nav */}
        {!colapsado && (
          <p className="text-[9px] font-bold tracking-widest px-5 pt-5 pb-2" style={{ color: '#3d444d' }}>MENÚ</p>
        )}
        <nav className={`space-y-0.5 px-2 ${colapsado ? 'mt-4' : 'mt-1'}`}>
          {links.map(link => (
            <NavLink
              key={link.to}
              to={link.to}
              className={({ isActive }) =>
                `w-full flex items-center gap-3 px-3 py-2.5 text-xs font-semibold rounded-lg transition-all relative whitespace-nowrap ${
                  isActive
                    ? 'text-[#22c55e]'
                    : 'hover:text-white'
                }`
              }
              style={({ isActive }) => isActive
                ? { backgroundColor: 'rgba(34,197,94,0.08)', color: '#22c55e' }
                : { color: '#8b949e' }
              }
            >
              {({ isActive }) => (
                <>
                  {isActive && (
                    <span className="absolute left-0 top-1.5 bottom-1.5 w-0.5 rounded-r" style={{ backgroundColor: '#22c55e' }} />
                  )}
                  {link.icon}
                  {!colapsado && <span>{link.label}</span>}
                </>
              )}
            </NavLink>
          ))}
        </nav>
      </div>

      {/* Bottom */}
      <div className="overflow-hidden" style={{ borderTop: '1px solid #21262d' }}>
        {!colapsado && (
          <button
            onClick={logout}
            className="w-full flex items-center gap-2 px-5 py-3 text-xs font-semibold transition-colors hover:opacity-80"
            style={{ color: '#f97316' }}
          >
            <svg className="w-4 h-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
            </svg>
            Cerrar sesión
          </button>
        )}
        <div className="flex items-center gap-3 px-3 py-3">
          <div
            className="w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold shrink-0"
            style={{ backgroundColor: '#22c55e', color: '#0d1117' }}
          >
            {getInitials(userName)}
          </div>
          {!colapsado && (
            <div className="overflow-hidden">
              <p className="text-xs font-semibold text-white truncate">{userName}</p>
              <p className="text-[10px] capitalize" style={{ color: '#8b949e' }}>{user?.rol || 'Administrador'}</p>
            </div>
          )}
        </div>
      </div>

      {/* Collapse toggle */}
      <button
        onClick={() => setColapsado(!colapsado)}
        className="absolute -right-3 top-1/2 -translate-y-1/2 w-6 h-6 rounded-full flex items-center justify-center text-[10px] z-10 transition-colors"
        style={{ backgroundColor: '#161b22', border: '1px solid #21262d', color: '#8b949e' }}
      >
        {colapsado ? '›' : '‹'}
      </button>
    </aside>
  )
}
