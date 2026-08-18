import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import toast from 'react-hot-toast'

export default function SeleccionarSucursal() {
  const { user, loading: authLoading, sucursalesPermitidas, seleccionarSucursal } = useAuth()
  const navigate = useNavigate()
  const [loading, setLoading] = useState(null)

  // Solo tiene sentido esta pantalla recién logueado con 2+ opciones; cualquier otro
  // caso (sesión perdida, entrada directa por URL) manda de vuelta a donde corresponda.
  useEffect(() => {
    if (authLoading) return
    if (!user) navigate('/login', { replace: true })
    else if (!sucursalesPermitidas || sucursalesPermitidas.length < 2) navigate('/', { replace: true })
  }, [authLoading, user, sucursalesPermitidas, navigate])

  if (authLoading || !user || !sucursalesPermitidas || sucursalesPermitidas.length < 2) return null

  const elegir = async sucursalId => {
    setLoading(sucursalId)
    try {
      const payload = await seleccionarSucursal(sucursalId)
      const esAdmin = payload?.rol === 'admin' || payload?.rol === 'superadmin'
      navigate(esAdmin ? '/dashboard' : '/checkin')
    } catch {
      toast.error('No se pudo seleccionar la sucursal')
      setLoading(null)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center" style={{ backgroundColor: '#0d1117' }}>
      <div className="w-full max-w-sm px-4">
        <div className="rounded-2xl p-8" style={{ backgroundColor: '#161b22', border: '1px solid #21262d' }}>
          <h2 className="text-white font-bold text-lg mb-1">¿En qué sucursal trabajas hoy?</h2>
          <p className="text-[#8b949e] text-xs mb-6">Toda tu sesión quedará asignada a esa sucursal.</p>

          <div className="space-y-2">
            {sucursalesPermitidas.map(s => (
              <button
                key={s.id}
                onClick={() => elegir(s.id)}
                disabled={loading !== null}
                className="w-full flex items-center justify-between px-4 py-3 rounded-lg text-sm font-semibold text-white transition-colors disabled:opacity-60"
                style={{ backgroundColor: '#0d1117', border: '1px solid #21262d' }}
              >
                <span>{s.nombre}</span>
                {loading === s.id && <span className="text-xs text-[#22c55e]">Entrando…</span>}
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
