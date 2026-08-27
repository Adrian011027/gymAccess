import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { T } from '../components/layout/saasTheme'
import toast from 'react-hot-toast'

const input = {
  backgroundColor: '#0a0d18', border: `1px solid ${T.borde}`, color: T.texto,
  borderRadius: '8px', padding: '10px 12px', fontSize: '13px', width: '100%', outline: 'none',
}

/**
 * Login exclusivo de la consola del SaaS, en su propia URL.
 *
 * No es el mismo formulario que `/login` con otro título: comparten esa ruta el
 * dueño de un gimnasio y su recepción, así que cualquiera que la encuentre puede
 * intentar credenciales ahí. Separar la URL evita que alguien topándose con `/login`
 * sepa siquiera que existe un panel por encima del de un negocio. Y a la inversa,
 * una cuenta que no es superadmin no entra por aquí aunque acierte la contraseña.
 */
export default function SaasLogin() {
  const { login, logout } = useAuth()
  const navigate = useNavigate()
  const [form, setForm] = useState({ email: '', password: '' })
  const [loading, setLoading] = useState(false)

  const submit = async e => {
    e.preventDefault()
    setLoading(true)
    try {
      const payload = await login(form.email, form.password)
      if (payload?.rol !== 'superadmin') {
        logout()
        toast.error('Esta cuenta no tiene acceso a la consola del SaaS')
        return
      }
      navigate('/saas')
    } catch {
      toast.error('Credenciales incorrectas')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center" style={{ backgroundColor: T.fondo }}>
      <div className="w-full max-w-sm px-4">
        <div className="flex flex-col items-center mb-8">
          <div className="w-14 h-14 rounded-xl flex items-center justify-center mb-4 font-black text-xl"
            style={{ background: `linear-gradient(135deg, ${T.acentoFuerte}, #a855f7)`, color: '#fff' }}>
            G
          </div>
          <h1 className="text-lg font-black tracking-widest" style={{ color: T.texto }}>GYMACCESS</h1>
          <p className="text-[10px] font-bold tracking-[0.2em] mt-1" style={{ color: T.acento }}>
            CONSOLA DEL SAAS
          </p>
        </div>

        <div className="rounded-2xl p-8" style={{ backgroundColor: T.panel, border: `1px solid ${T.borde}` }}>
          <h2 className="font-bold text-lg mb-1" style={{ color: T.texto }}>Acceso de administrador</h2>
          <p className="text-xs mb-6" style={{ color: T.tenue }}>Solo cuentas superadmin</p>

          <form onSubmit={submit} className="space-y-4">
            <div>
              <label className="text-[10px] font-semibold tracking-widest uppercase block mb-1.5" style={{ color: T.tenue }}>
                Correo electrónico
              </label>
              <input type="email" required value={form.email}
                onChange={e => setForm(f => ({ ...f, email: e.target.value }))}
                placeholder="tu@gymaccess.com" style={input} />
            </div>

            <div>
              <label className="text-[10px] font-semibold tracking-widest uppercase block mb-1.5" style={{ color: T.tenue }}>
                Contraseña
              </label>
              <input type="password" required value={form.password}
                onChange={e => setForm(f => ({ ...f, password: e.target.value }))}
                placeholder="••••••••" style={input} />
            </div>

            <button type="submit" disabled={loading}
              className="w-full py-3 rounded-lg font-bold text-sm transition-all mt-2 disabled:opacity-60"
              style={{ backgroundColor: T.acentoFuerte, color: '#fff' }}>
              {loading ? 'Verificando…' : 'Entrar a la consola'}
            </button>
          </form>
        </div>

        <p className="text-center text-xs mt-6" style={{ color: T.apagado }}>
          ¿Eres dueño de un gimnasio? <Link to="/login" style={{ color: T.acento }}>Entra por aquí</Link>
        </p>
      </div>
    </div>
  )
}
