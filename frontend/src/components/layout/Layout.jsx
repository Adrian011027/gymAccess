import { useState } from 'react'
import { Navigate, Outlet, useNavigate } from 'react-router-dom'
import { useAuth } from '../../context/AuthContext'
import Sidebar from './Sidebar'
import Navbar from './Navbar'
import AceptacionLegal from '../AceptacionLegal'

export default function Layout() {
  const { user, loading, enSoporte, volverAlPanel } = useAuth()
  const [colapsado, setColapsado] = useState(false)
  const [mobileOpen, setMobileOpen] = useState(false)
  const navigate = useNavigate()

  if (loading) return (
    <div className="min-h-screen flex items-center justify-center" style={{ backgroundColor: '#0d1117' }}>
      <div className="text-[#22c55e] text-sm font-bold tracking-widest">Cargando...</div>
    </div>
  )
  if (!user) return <Navigate to="/login" replace />

  return (
    <div className="flex h-screen w-full overflow-hidden" style={{ backgroundColor: '#0d1117' }}>
      {/* Va aquí y no en cada página: envuelve todas las rutas autenticadas, así que
          no hay pantalla desde la que se pueda esquivar. */}
      <AceptacionLegal />
      <Sidebar
        colapsado={colapsado}
        setColapsado={setColapsado}
        mobileOpen={mobileOpen}
        setMobileOpen={setMobileOpen}
      />
      <div className="flex-1 flex flex-col overflow-hidden min-w-0">
        {/* Operar como otro sin saberlo es como se toca por error la base de un
            cliente. La franja no se puede ignorar y lleva la salida encima. */}
        {enSoporte && (
          <div className="flex items-center justify-between gap-3 px-4 py-2 shrink-0"
            style={{ backgroundColor: '#f97316', color: '#0d1117' }}>
            <p className="text-[11px] font-bold">
              Sesión de soporte · estás operando como {user?.nombre} ({user?.email})
            </p>
            <button onClick={() => { if (volverAlPanel()) navigate('/saas') }}
              className="text-[11px] font-bold underline shrink-0">
              Volver al panel del SaaS
            </button>
          </div>
        )}
        <Navbar onMenuClick={() => setMobileOpen(true)} />
        <main className="flex-1 overflow-y-auto p-4 sm:p-6">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
