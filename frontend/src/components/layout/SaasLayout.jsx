import { Navigate, NavLink, Outlet } from 'react-router-dom'
import { useAuth } from '../../context/AuthContext'
import { T } from './saasTheme'

/**
 * Chrome propio de la consola del SaaS.
 *
 * No reutiliza `Layout` a propósito. Aquel es el chrome de *un gimnasio*: su sidebar
 * lleva Check-In, Socios y Clases, que para el dueño del producto salen vacíos porque
 * su usuario no tiene gym. Y más importante que lo vacío: esta consola opera *sobre*
 * los clientes —suspende cuentas, entra como ellos—, así que tiene que verse distinta
 * de la pantalla donde uno cobra una mensualidad. La paleta índigo contra el verde del
 * gimnasio es la señal de "estás una capa más arriba", no decoración.
 */

const NAV = [
  { to: '/saas', label: 'Gimnasios', end: true },
  { to: '/saas/soporte', label: 'Soporte' },
]

export default function SaasLayout() {
  const { user, loading, esSuperAdmin, logout } = useAuth()

  if (loading) return (
    <div className="min-h-screen flex items-center justify-center" style={{ backgroundColor: T.fondo }}>
      <div className="text-sm font-bold tracking-[0.2em]" style={{ color: T.acento }}>CARGANDO</div>
    </div>
  )
  if (!user) return <Navigate to="/saas/login" replace />
  if (!esSuperAdmin) return <Navigate to="/" replace />

  return (
    <div className="min-h-screen flex flex-col" style={{ backgroundColor: T.fondo, color: T.texto }}>
      <header className="shrink-0" style={{ borderBottom: `1px solid ${T.borde}`, backgroundColor: T.panel }}>
        <div className="max-w-[1400px] mx-auto px-5 py-3 flex items-center justify-between gap-4 flex-wrap">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg flex items-center justify-center font-black text-sm shrink-0"
              style={{ background: `linear-gradient(135deg, ${T.acentoFuerte}, #a855f7)`, color: '#fff' }}>
              G
            </div>
            <div>
              <p className="text-sm font-bold leading-tight">GymAccess</p>
              <p className="text-[9px] font-bold tracking-[0.18em]" style={{ color: T.acento }}>
                CONSOLA DEL SAAS
              </p>
            </div>
          </div>

          <nav className="flex items-center gap-1 order-3 w-full sm:order-2 sm:w-auto">
            {NAV.map(n => (
              <NavLink key={n.to} to={n.to} end={n.end}
                className="px-3 py-1.5 rounded-lg text-[11px] font-bold transition-colors"
                style={({ isActive }) => ({
                  backgroundColor: isActive ? T.acentoFuerte : 'transparent',
                  color: isActive ? '#fff' : T.tenue,
                })}>
                {n.label}
              </NavLink>
            ))}
          </nav>

          <div className="flex items-center gap-3 order-2 sm:order-3">
            <div className="text-right hidden sm:block">
              <p className="text-[11px] font-semibold leading-tight">{user.nombre}</p>
              <p className="text-[9px]" style={{ color: T.apagado }}>{user.email}</p>
            </div>
            <button onClick={logout}
              className="px-3 py-1.5 rounded-lg text-[10px] font-bold transition-colors"
              style={{ border: `1px solid ${T.borde}`, color: T.tenue }}>
              Salir
            </button>
          </div>
        </div>
      </header>

      <main className="flex-1 w-full max-w-[1400px] mx-auto px-5 py-6">
        <Outlet />
      </main>
    </div>
  )
}
