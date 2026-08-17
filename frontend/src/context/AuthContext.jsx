import { createContext, useContext, useState, useEffect } from 'react'
import api from '../api/axios'
import { leerToken } from '../lib/jwt'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    // Un token corrupto o truncado en localStorage reventaba aquí y dejaba la pantalla
    // en blanco, sin forma de salir salvo limpiar el navegador a mano.
    const payload = leerToken(localStorage.getItem('access'))
    if (payload) setUser(payload)
    else localStorage.removeItem('access')
    setLoading(false)
  }, [])

  const login = async (email, password) => {
    const { data } = await api.post('/auth/login/', { email, password })
    const payload = leerToken(data.access)
    if (!payload) throw new Error('El servidor devolvió un token inválido')
    localStorage.setItem('access', data.access)
    localStorage.setItem('refresh', data.refresh)
    setUser(payload)
    return payload
  }

  const logout = () => {
    localStorage.clear()
    setUser(null)
  }

  const isAdmin = user?.rol === 'admin' || user?.rol === 'superadmin'
  const isCoach = user?.rol === 'coach'
  // El coach da clases, no cobra: la caja le queda fuera igual que al público.
  const puedeCobrar = !!user && !isCoach

  return (
    <AuthContext.Provider
      value={{ user, isAdmin, isCoach, puedeCobrar, login, logout, loading }}
    >
      {children}
    </AuthContext.Provider>
  )
}

export const useAuth = () => useContext(AuthContext)
