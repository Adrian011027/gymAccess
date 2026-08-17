import { BrowserRouter, Routes, Route, Navigate, Outlet } from 'react-router-dom'
import { Toaster } from 'react-hot-toast'
import { AuthProvider, useAuth } from './context/AuthContext'
import Layout from './components/layout/Layout'
import Login from './pages/Login'
import CheckIn from './pages/CheckIn'
import Dashboard from './pages/Dashboard'
import Socios from './pages/Socios'
import Clases from './pages/Clases'
import Equipamiento from './pages/Equipamiento'
import Reportes from './pages/Reportes'
import Pagos from './pages/Pagos'
import Configuracion from './pages/Configuracion'
import Notificaciones from './pages/Notificaciones'

// Cada rol aterriza donde trabaja: el admin en el dashboard, recepción en el mostrador,
// el coach en su horario de clases.
function inicioDe({ isAdmin, isCoach }) {
  if (isAdmin) return '/dashboard'
  return isCoach ? '/clases' : '/checkin'
}

function HomeRedirect() {
  return <Navigate to={inicioDe(useAuth())} replace />
}

// Bloquea los módulos financieros/administrativos a quien no es admin.
function AdminRoutes() {
  const auth = useAuth()
  return auth.isAdmin ? <Outlet /> : <Navigate to={inicioDe(auth)} replace />
}

// La caja: todos menos el coach.
function CajaRoutes() {
  const auth = useAuth()
  return auth.puedeCobrar ? <Outlet /> : <Navigate to={inicioDe(auth)} replace />
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Toaster
          position="top-right"
          toastOptions={{
            style: { background: '#161b22', color: '#fff', border: '1px solid #21262d' },
            success: { iconTheme: { primary: '#22c55e', secondary: '#0d1117' } },
          }}
        />
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route element={<Layout />}>
            <Route path="/" element={<HomeRedirect />} />
            <Route path="/checkin"      element={<CheckIn />} />
            <Route path="/socios"       element={<Socios />} />
            <Route path="/clases"       element={<Clases />} />
            <Route path="/notificaciones" element={<Notificaciones />} />
            <Route element={<CajaRoutes />}>
              <Route path="/pagos"      element={<Pagos />} />
            </Route>
            <Route element={<AdminRoutes />}>
              <Route path="/dashboard"    element={<Dashboard />} />
              <Route path="/equipamiento" element={<Equipamiento />} />
              <Route path="/reportes"     element={<Reportes />} />
              <Route path="/configuracion" element={<Configuracion />} />
            </Route>
            <Route path="*" element={<HomeRedirect />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  )
}
