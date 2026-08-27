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
import POS from './pages/POS'
import Configuracion from './pages/Configuracion'
import Notificaciones from './pages/Notificaciones'
import Empleados from './pages/Empleados'
import Legal from './pages/Legal'
import SeleccionarSucursal from './pages/SeleccionarSucursal'
import Saas from './pages/Saas'
import SaasSoporte from './pages/SaasSoporte'
import SaasLayout from './components/layout/SaasLayout'

// El dueño del SaaS aterriza en su panel; el admin de un gimnasio en el dashboard;
// recepción va directo al check-in.
function HomeRedirect() {
  const { isAdmin, esSuperAdmin } = useAuth()
  if (esSuperAdmin) return <Navigate to="/saas" replace />
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
          <Route path="/seleccionar-sucursal" element={<SeleccionarSucursal />} />
          <Route path="/saas" element={<SaasLayout />}>
            <Route index element={<Saas />} />
            <Route path="soporte" element={<SaasSoporte />} />
          </Route>
          <Route element={<Layout />}>
            <Route path="/" element={<HomeRedirect />} />
            <Route path="/checkin"      element={<CheckIn />} />
            <Route path="/socios"       element={<Socios />} />
            <Route path="/clases"       element={<Clases />} />
            <Route path="/pagos"        element={<Pagos />} />
            <Route path="/pos"          element={<POS />} />
            <Route path="/notificaciones" element={<Notificaciones />} />
            <Route element={<AdminRoutes />}>
              <Route path="/dashboard"    element={<Dashboard />} />
              <Route path="/equipamiento" element={<Equipamiento />} />
              <Route path="/reportes"     element={<Reportes />} />
              <Route path="/configuracion" element={<Configuracion />} />
              <Route path="/empleados"    element={<Empleados />} />
              <Route path="/legal"        element={<Legal />} />
            </Route>
          </Route>
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  )
}
