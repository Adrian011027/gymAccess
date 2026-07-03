import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import toast from 'react-hot-toast'

export default function Login() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const [form, setForm] = useState({ email: '', password: '' })
  const [showPassword, setShowPassword] = useState(false)
  const [loading, setLoading] = useState(false)

  const submit = async e => {
    e.preventDefault()
    setLoading(true)
    try {
      await login(form.email, form.password)
      navigate('/dashboard')
    } catch {
      toast.error('Credenciales incorrectas')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center" style={{ backgroundColor: '#0d1117' }}>
      <div className="w-full max-w-sm px-4">
        {/* Logo */}
        <div className="flex flex-col items-center mb-8">
          <div className="w-20 h-20 rounded-full flex items-center justify-center mb-4 border-2 border-[#22c55e]" style={{ backgroundColor: '#161b22' }}>
            <svg className="w-10 h-10 text-[#22c55e]" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                d="M9 12l2 2 4-4M7.835 4.697a3.42 3.42 0 001.946-.806 3.42 3.42 0 014.438 0 3.42 3.42 0 001.946.806 3.42 3.42 0 013.138 3.138 3.42 3.42 0 00.806 1.946 3.42 3.42 0 010 4.438 3.42 3.42 0 00-.806 1.946 3.42 3.42 0 01-3.138 3.138 3.42 3.42 0 00-1.946.806 3.42 3.42 0 01-4.438 0 3.42 3.42 0 00-1.946-.806 3.42 3.42 0 01-3.138-3.138 3.42 3.42 0 00-.806-1.946 3.42 3.42 0 010-4.438 3.42 3.42 0 00.806-1.946 3.42 3.42 0 013.138-3.138z" />
            </svg>
          </div>
          <h1 className="text-2xl font-black tracking-widest text-white">ROUND3BOXING</h1>
          <p className="text-xs text-[#22c55e] font-semibold tracking-widest mt-1">GYM SYSTEM</p>
        </div>

        {/* Card */}
        <div className="rounded-2xl p-8" style={{ backgroundColor: '#161b22', border: '1px solid #21262d' }}>
          <h2 className="text-white font-bold text-lg mb-1">Iniciar sesión</h2>
          <p className="text-[#8b949e] text-xs mb-6">Panel de administración</p>

          <form onSubmit={submit} className="space-y-4">
            <div>
              <label className="text-[10px] font-semibold tracking-widest text-[#8b949e] uppercase block mb-1.5">
                Correo electrónico
              </label>
              <div className="flex items-center gap-2 px-3 py-2.5 rounded-lg" style={{ backgroundColor: '#0d1117', border: '1px solid #21262d' }}>
                <svg className="w-4 h-4 text-[#8b949e] shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                </svg>
                <input
                  type="email"
                  required
                  value={form.email}
                  onChange={e => setForm(f => ({ ...f, email: e.target.value }))}
                  placeholder="admin@round3boxing.com"
                  className="bg-transparent text-white text-sm w-full outline-none placeholder:text-[#3d444d]"
                />
              </div>
            </div>

            <div>
              <label className="text-[10px] font-semibold tracking-widest text-[#8b949e] uppercase block mb-1.5">
                Contraseña
              </label>
              <div className="flex items-center gap-2 px-3 py-2.5 rounded-lg" style={{ backgroundColor: '#0d1117', border: '1px solid #21262d' }}>
                <svg className="w-4 h-4 text-[#8b949e] shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
                </svg>
                <input
                  type={showPassword ? 'text' : 'password'}
                  required
                  value={form.password}
                  onChange={e => setForm(f => ({ ...f, password: e.target.value }))}
                  placeholder="••••••••"
                  className="bg-transparent text-white text-sm w-full outline-none placeholder:text-[#3d444d]"
                />
                <button type="button" onClick={() => setShowPassword(p => !p)} className="text-[#8b949e] hover:text-white transition-colors">
                  {showPassword
                    ? <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l3.59 3.59m0 0A9.953 9.953 0 0112 5c4.478 0 8.268 2.943 9.543 7a10.025 10.025 0 01-4.132 5.411m0 0L21 21" /></svg>
                    : <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" /><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" /></svg>
                  }
                </button>
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full py-3 rounded-lg font-bold text-sm text-white transition-all mt-2 disabled:opacity-60"
              style={{ backgroundColor: '#22c55e' }}
              onMouseEnter={e => { if (!loading) e.currentTarget.style.backgroundColor = '#16a34a' }}
              onMouseLeave={e => { if (!loading) e.currentTarget.style.backgroundColor = '#22c55e' }}
            >
              {loading ? 'Verificando...' : 'Entrar al sistema'}
            </button>
          </form>
        </div>

        <p className="text-center text-xs mt-6" style={{ color: '#3d444d' }}>
          © 2025 Round3Boxing — Todos los derechos reservados
        </p>
      </div>
    </div>
  )
}
