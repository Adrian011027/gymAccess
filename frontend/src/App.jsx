import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { Toaster } from 'react-hot-toast'
import { AuthProvider } from './context/AuthContext'
import Layout from './components/layout/Layout'
import Login from './pages/Login'
import Dashboard from './pages/Dashboard'
import Socios from './pages/Socios'
import Clases from './pages/Clases'
import Equipamiento from './pages/Equipamiento'
import Reportes from './pages/Reportes'
import Pagos from './pages/Pagos'
import Configuracion from './pages/Configuracion'

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
            <Route path="/" element={<Navigate to="/dashboard" replace />} />
            <Route path="/dashboard"    element={<Dashboard />} />
            <Route path="/socios"       element={<Socios />} />
            <Route path="/clases"       element={<Clases />} />
            <Route path="/equipamiento" element={<Equipamiento />} />
            <Route path="/reportes"     element={<Reportes />} />
            <Route path="/pagos"        element={<Pagos />} />
            <Route path="/configuracion" element={<Configuracion />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  )
}
