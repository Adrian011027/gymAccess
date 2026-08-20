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

  const logout = () => {
    localStorage.clear()
    setUser(null)
  }

  const isAdmin = user?.rol === 'admin' || user?.rol === 'superadmin'
  // null = opera todo el gym (el dueño). Con valor = atado a esa sucursal.
  const sucursalId = user?.sucursal_id ?? null
  const sucursalNombre = user?.sucursal_nombre ?? null
  const verTodasLasSucursales = sucursalId === null
  const sucursalesPermitidas = user?.sucursales_permitidas ?? []

  return (
    <AuthContext.Provider value={{
      user, isAdmin, login, logout, loading, seleccionarSucursal,
      sucursalId, sucursalNombre, verTodasLasSucursales, sucursalesPermitidas,
    }}>
      {children}
    </AuthContext.Provider>
  )
}

export const useAuth = () => useContext(AuthContext)
