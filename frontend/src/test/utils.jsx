import { render } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { AuthProvider } from '../context/AuthContext'

/** Arma un JWT de mentiras con el payload que se le pase. La firma no se valida en el
 *  frontend, así que basta con que las tres partes existan y el payload sea base64. */
export function tokenFalso(payload) {
  const b64 = obj => btoa(JSON.stringify(obj)).replace(/=+$/, '')
  return `${b64({ alg: 'HS256', typ: 'JWT' })}.${b64(payload)}.firma-de-mentiras`
}

export const USUARIOS = {
  superadmin: { nombre: 'Super', email: 'super@r3b.com', rol: 'superadmin', gym_id: 1 },
  admin: { nombre: 'Diego', email: 'diego@r3b.com', rol: 'admin', gym_id: 1 },
  recepcion: { nombre: 'Rosa', email: 'rosa@r3b.com', rol: 'recepcion', gym_id: 1 },
  coach: { nombre: 'Carlos', email: 'carlos@r3b.com', rol: 'coach', gym_id: 1 },
}

/** Deja una sesión iniciada en localStorage antes de montar el componente. */
export function iniciarSesion(rol) {
  localStorage.setItem('access', tokenFalso(USUARIOS[rol]))
  localStorage.setItem('refresh', tokenFalso({ ...USUARIOS[rol], tipo: 'refresh' }))
}

/** Monta con router y sesión, que es como viven casi todos los componentes. */
export function renderConSesion(ui, { rol = 'admin', ruta = '/' } = {}) {
  if (rol) iniciarSesion(rol)
  return render(
    <AuthProvider>
      <MemoryRouter initialEntries={[ruta]}>{ui}</MemoryRouter>
    </AuthProvider>,
  )
}
