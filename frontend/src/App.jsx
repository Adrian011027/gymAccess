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

// El admin aterriza en el dashboard; recepción va directo al check-in.
function HomeRedirect() {
  const { isAdmin } = useAuth()
  return <Navigate to={isAdmin ? '/dashboard' : '/checkin'} replace />
}

// Bloquea los módulos financieros/administrativos a quien no es admin.
function AdminRoutes() {
  const { isAdmin } = useAuth()
  return isAdmin ? <Outlet /> : <Navigate to="/checkin" replace />
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
            <Route path="/pagos"        element={<Pagos />} />
            <Route element={<AdminRoutes />}>
              <Route path="/dashboard"    element={<Dashboard />} />
              <Route path="/equipamiento" element={<Equipamiento />} />
              <Route path="/reportes"     element={<Reportes />} />
              <Route path="/configuracion" element={<Configuracion />} />
            </Route>
          </Route>
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  )
}
