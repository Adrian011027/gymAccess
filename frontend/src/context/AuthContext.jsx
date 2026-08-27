import { createContext, useContext, useState, useEffect } from 'react'
import api from '../api/axios'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const token = localStorage.getItem('access')
    if (token) {
      const payload = JSON.parse(atob(token.split('.')[1]))
      setUser(payload)
    }
    setLoading(false)
  }, [])

  const login = async (email, password) => {
    const { data } = await api.post('/auth/login/', { email, password })
    localStorage.setItem('access', data.access)
    localStorage.setItem('refresh', data.refresh)
    const payload = JSON.parse(atob(data.access.split('.')[1]))
    setUser(payload)
    return payload
  }

  // Recepción con 2+ sucursales permitidas la usa para elegir con cuál entra;
  // reemite tokens (igual que login) porque AuthContext solo decodifica el JWT.
  const seleccionarSucursal = async sucursalId => {
    const { data } = await api.post('/usuarios/sucursal-activa/', { sucursal: sucursalId })
    localStorage.setItem('access', data.access)
    localStorage.setItem('refresh', data.refresh)
    const payload = JSON.parse(atob(data.access.split('.')[1]))
    setUser(payload)
    return payload
  }

  // Soporte: el dueño del SaaS entra como el admin de un gimnasio. Su propio token
  // se guarda aparte para poder volver sin re-loguearse; si se perdiera, saldría del
  // panel cada vez que atiende a un cliente.
  const entrarComoSoporte = (access, refresh) => {
    localStorage.setItem('saas_access', localStorage.getItem('access'))
    localStorage.setItem('saas_refresh', localStorage.getItem('refresh'))
    localStorage.setItem('access', access)
    localStorage.setItem('refresh', refresh)
    setUser(JSON.parse(atob(access.split('.')[1])))
  }

  const volverAlPanel = () => {
    const access = localStorage.getItem('saas_access')
    const refresh = localStorage.getItem('saas_refresh')
    if (!access) return false
    localStorage.setItem('access', access)
    localStorage.setItem('refresh', refresh)
    localStorage.removeItem('saas_access')
    localStorage.removeItem('saas_refresh')
    setUser(JSON.parse(atob(access.split('.')[1])))
    return true
  }

  const logout = () => {
    localStorage.clear()
    setUser(null)
  }

  const isAdmin = user?.rol === 'admin' || user?.rol === 'superadmin'
  // El dueño del SaaS. Se distingue de `isAdmin` a propósito: ese mete en el mismo
  // saco al dueño de un gimnasio, que no debe ver el panel del negocio completo.
  const esSuperAdmin = user?.rol === 'superadmin'
  // Sesión prestada: el token lo emitió `/saas/tenants/<id>/impersonar/`.
  const enSoporte = !!user?.soporte
  // null = opera todo el gym (el dueño). Con valor = atado a esa sucursal.
  const sucursalId = user?.sucursal_id ?? null
  const sucursalNombre = user?.sucursal_nombre ?? null
  const verTodasLasSucursales = sucursalId === null
  const sucursalesPermitidas = user?.sucursales_permitidas ?? []

  return (
    <AuthContext.Provider value={{
      user, isAdmin, login, logout, loading, seleccionarSucursal,
      sucursalId, sucursalNombre, verTodasLasSucursales, sucursalesPermitidas,
      esSuperAdmin, enSoporte, entrarComoSoporte, volverAlPanel,
    }}>
      {children}
    </AuthContext.Provider>
  )
}

export const useAuth = () => useContext(AuthContext)
