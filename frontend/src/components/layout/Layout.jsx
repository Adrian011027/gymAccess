import { useState } from 'react'
import { Navigate, Outlet } from 'react-router-dom'
import { useAuth } from '../../context/AuthContext'
import Sidebar from './Sidebar'
import Navbar from './Navbar'

export default function Layout() {
  const { user, loading } = useAuth()
  const [colapsado, setColapsado] = useState(false)

  if (loading) return (
    <div className="min-h-screen flex items-center justify-center" style={{ backgroundColor: '#0d1117' }}>
      <div className="text-[#22c55e] text-sm font-bold tracking-widest">Cargando...</div>
    </div>
  )
  if (!user) return <Navigate to="/login" replace />

  return (
    <div className="flex h-screen w-screen overflow-hidden" style={{ backgroundColor: '#0d1117' }}>
      <Sidebar colapsado={colapsado} setColapsado={setColapsado} />
      <div className="flex-1 flex flex-col overflow-hidden">
        <Navbar colapsado={colapsado} />
        <main className="flex-1 overflow-y-auto p-6">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
