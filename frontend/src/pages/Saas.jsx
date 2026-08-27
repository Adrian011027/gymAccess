import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import toast from 'react-hot-toast'
import api from '../api/axios'
import { useAuth } from '../context/AuthContext'
import { T } from '../components/layout/saasTheme'

const input = {
  backgroundColor: '#0a0d18', border: `1px solid ${T.borde}`, color: T.texto,
  borderRadius: '8px', padding: '9px 11px', fontSize: '13px', width: '100%', outline: 'none',
}
const panel = { backgroundColor: T.panel, border: `1px solid ${T.bordeSuave}` }

const TIPOS = [['box', 'Box / Artes marciales'], ['pesas', 'Gym de pesas'], ['mixto', 'Mixto']]
const TIPO_LABEL = Object.fromEntries(TIPOS)

const ALTA_EMPTY = {
  nombre: '', tipo: 'mixto', telefono: '', email_contacto: '', direccion: '',
  sucursal_nombre: 'Matriz', sucursal_direccion: '',
  admin_nombre: '', admin_email: '', admin_password: '',
}

export default function Saas() {
  const { entrarComoSoporte } = useAuth()
  const navigate = useNavigate()
  const [resumen, setResumen] = useState(null)
  const [tenants, setTenants] = useState([])
  const [filtro, setFiltro] = useState('todos')
  const [busca, setBusca] = useState('')
  const [alta, setAlta] = useState(false)
  const [form, setForm] = useState(ALTA_EMPTY)
  const [guardando, setGuardando] = useState(false)
  // Entrar como un cliente pide motivo: queda en la bitácora del backend y sin él
  // el registro no serviría para auditar nada.
  const [soporte, setSoporte] = useState(null)
  const [motivo, setMotivo] = useState('')
  const [soporteLoading, setSoporteLoading] = useState(false)

  const cargar = () => {
    api.get('/saas/resumen/').then(r => setResumen(r.data)).catch(() => {})
    api.get('/saas/tenants/').then(r => setTenants(r.data)).catch(() => {})
  }
  useEffect(cargar, [])

  const errorDe = err => {
    const d = err.response?.data
    if (typeof d === 'object' && d) return String(Object.values(d).flat()[0])
    return 'No se pudo completar la operación'
  }

  const visibles = tenants
    .filter(t => filtro === 'todos' || t.estado === filtro)
    .filter(t => !busca.trim() || t.nombre.toLowerCase().includes(busca.trim().toLowerCase()))

  const crear = async e => {
    e.preventDefault()
    setGuardando(true)
    try {
      const { data } = await api.post('/saas/tenants/', form)
      toast.success(`${data.gym.nombre} dado de alta`)
      setAlta(false)
      setForm(ALTA_EMPTY)
      cargar()
    } catch (err) {
      toast.error(errorDe(err))
    } finally {
      setGuardando(false)
    }
  }

  const cambiarEstado = async (t, accion) => {
    try {
      await api.post(`/saas/tenants/${t.id}/${accion}/`)
      toast.success(accion === 'suspender' ? `${t.nombre} suspendido` : `${t.nombre} reactivado`)
      cargar()
    } catch (err) {
      toast.error(errorDe(err))
    }
  }

  const entrar = async () => {
    if (!motivo.trim()) return
    setSoporteLoading(true)
    try {
      const { data } = await api.post(`/saas/tenants/${soporte.id}/impersonar/`, { motivo })
      entrarComoSoporte(data.access, data.refresh)
      toast.success(`Entrando como ${data.suplantado.nombre}`)
      navigate('/dashboard')
    } catch (err) {
      toast.error(errorDe(err))
    } finally {
      setSoporteLoading(false)
    }
  }

  // Cuatro números, no siete. Los que caben en la cabeza de un vistazo: cuántos
  // clientes hay, cuántos están caídos, cuánto pesan y cuánto se usa el producto.
  const HERO = resumen ? [
    { etiqueta: 'Gimnasios activos', valor: resumen.gyms_activos, pie: `${resumen.gyms_total} en total`, color: T.texto },
    {
      etiqueta: 'Suspendidos', valor: resumen.gyms_suspendidos,
      pie: resumen.gyms_suspendidos ? 'requieren atención' : 'ninguno',
      color: resumen.gyms_suspendidos ? T.alerta : T.apagado,
    },
    { etiqueta: 'Sucursales', valor: resumen.sucursales, pie: `${resumen.empleados} empleados`, color: T.texto },
    {
      etiqueta: 'Socios vigentes', valor: resumen.socios_vigentes,
      pie: `de ${resumen.socios} registrados`, color: T.acento,
    },
  ] : []

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        {HERO.map(m => (
          <div key={m.etiqueta} className="rounded-xl p-4 relative overflow-hidden" style={panel}>
            <div className="absolute inset-x-0 top-0 h-px"
              style={{ background: `linear-gradient(90deg, transparent, ${m.color}55, transparent)` }} />
            <p className="text-[9px] font-bold tracking-[0.16em]" style={{ color: T.tenue }}>
              {m.etiqueta.toUpperCase()}
            </p>
            <p className="text-3xl font-black mt-1.5 leading-none" style={{ color: m.color }}>{m.valor}</p>
            <p className="text-[10px] mt-1.5" style={{ color: T.apagado }}>{m.pie}</p>
          </div>
        ))}
      </div>

      <div className="rounded-xl overflow-hidden" style={panel}>
        <div className="px-4 py-3 flex items-center justify-between gap-3 flex-wrap"
          style={{ borderBottom: `1px solid ${T.bordeSuave}`, backgroundColor: T.panelAlto }}>
          <div className="flex items-center gap-2 flex-wrap">
            {[['todos', 'Todos'], ['activo', 'Activos'], ['suspendido', 'Suspendidos']].map(([c, etiqueta]) => {
              const n = c === 'todos' ? tenants.length : tenants.filter(t => t.estado === c).length
              const on = filtro === c
              return (
                <button key={c} onClick={() => setFiltro(c)}
                  className="px-2.5 py-1 rounded-md text-[10px] font-bold transition-colors"
                  style={{
                    backgroundColor: on ? T.acentoFuerte : 'transparent',
                    color: on ? '#fff' : T.tenue,
                    border: `1px solid ${on ? T.acentoFuerte : T.borde}`,
                  }}>
                  {etiqueta} <span style={{ opacity: 0.65 }}>{n}</span>
                </button>
              )
            })}
            <input value={busca} onChange={e => setBusca(e.target.value)} placeholder="Buscar gimnasio…"
              style={{ ...input, width: '180px', padding: '5px 10px', fontSize: '11px' }} />
          </div>
          <button onClick={() => { setForm(ALTA_EMPTY); setAlta(true) }}
            className="px-3.5 py-1.5 rounded-lg text-[11px] font-bold shrink-0"
            style={{ backgroundColor: T.acentoFuerte, color: '#fff' }}>
            + Nuevo gimnasio
          </button>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full" style={{ minWidth: '860px' }}>
            <thead>
              <tr style={{ borderBottom: `1px solid ${T.bordeSuave}` }}>
                {['Gimnasio', 'Estado', 'Dueño', 'Suc.', 'Empl.', 'Socios', 'Vigentes', ''].map((h, i) => (
                  <th key={h || i}
                    className={`text-[9px] font-bold tracking-[0.14em] px-4 py-2.5 ${i >= 3 && i <= 6 ? 'text-right' : 'text-left'}`}
                    style={{ color: T.apagado }}>
                    {h.toUpperCase()}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {visibles.map(t => (
                <tr key={t.id} style={{ borderBottom: `1px solid ${T.bordeSuave}` }}>
                  <td className="px-4 py-3">
                    <p className="text-[13px] font-bold leading-tight">{t.nombre}</p>
                    <p className="text-[10px]" style={{ color: T.apagado }}>
                      {TIPO_LABEL[t.tipo] ?? t.tipo}
                    </p>
                  </td>
                  <td className="px-4 py-3">
                    <span className="inline-flex items-center gap-1.5 text-[10px] font-bold">
                      <span className="w-1.5 h-1.5 rounded-full"
                        style={{ backgroundColor: t.activo ? T.ok : T.alerta }} />
                      <span style={{ color: t.activo ? T.ok : T.alerta }}>
                        {t.activo ? 'Activo' : 'Suspendido'}
                      </span>
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    {t.admin ? (
                      <>
                        <p className="text-[11px] leading-tight">{t.admin.nombre}</p>
                        <p className="text-[10px]" style={{ color: T.apagado }}>{t.admin.email}</p>
                      </>
                    ) : (
                      <span className="text-[10px] font-bold" style={{ color: T.aviso }}>sin admin activo</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-right text-[12px] tabular-nums">{t.sucursales}</td>
                  <td className="px-4 py-3 text-right text-[12px] tabular-nums">{t.empleados}</td>
                  <td className="px-4 py-3 text-right text-[12px] tabular-nums">{t.socios}</td>
                  <td className="px-4 py-3 text-right text-[12px] font-bold tabular-nums" style={{ color: T.acento }}>
                    {t.socios_vigentes}
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center justify-end gap-3 whitespace-nowrap">
                      <button onClick={() => { setSoporte(t); setMotivo('') }}
                        className="text-[10px] font-bold transition-colors"
                        style={{ color: T.tenue }}
                        onMouseEnter={e => e.currentTarget.style.color = T.acento}
                        onMouseLeave={e => e.currentTarget.style.color = T.tenue}>
                        Entrar como
                      </button>
                      <button onClick={() => cambiarEstado(t, t.activo ? 'suspender' : 'reactivar')}
                        className="text-[10px] font-bold transition-colors"
                        style={{ color: t.activo ? T.tenue : T.ok }}
                        onMouseEnter={e => { if (t.activo) e.currentTarget.style.color = T.alerta }}
                        onMouseLeave={e => { if (t.activo) e.currentTarget.style.color = T.tenue }}>
                        {t.activo ? 'Suspender' : 'Reactivar'}
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {visibles.length === 0 && (
            <p className="text-[11px] text-center py-8" style={{ color: T.apagado }}>
              {tenants.length === 0 ? 'Sin gimnasios dados de alta' : 'Nada coincide con el filtro'}
            </p>
          )}
        </div>
      </div>

      {/* Alta: gym + primera sucursal + admin. El backend los crea en una sola
          transacción, así que o entran los tres o no entra ninguno. */}
      {alta && (
        <div className="fixed inset-0 z-50 flex overflow-y-auto p-4" style={{ backgroundColor: 'rgba(4,6,12,0.82)' }}>
          <form onSubmit={crear}
            className="w-full max-w-lg mx-auto my-auto rounded-xl p-5 space-y-3 max-h-[90vh] overflow-y-auto"
            style={{ backgroundColor: T.panel, border: `1px solid ${T.borde}` }}>
            <div>
              <h2 className="text-sm font-bold">Nuevo gimnasio</h2>
              <p className="text-[10px] mt-1 leading-relaxed" style={{ color: T.tenue }}>
                Se crea el gimnasio, su primera sucursal y el usuario de su dueño. Sin
                admin nadie puede entrar a operarlo, por eso los tres van juntos.
              </p>
            </div>

            <div>
              <label className="text-[9px] font-bold tracking-[0.14em]" style={{ color: T.tenue }}>
                NOMBRE DEL GIMNASIO *
              </label>
              <input required value={form.nombre} style={input}
                onChange={e => setForm(f => ({ ...f, nombre: e.target.value }))} />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-[9px] font-bold tracking-[0.14em]" style={{ color: T.tenue }}>TIPO</label>
                <select value={form.tipo} style={input}
                  onChange={e => setForm(f => ({ ...f, tipo: e.target.value }))}>
                  {TIPOS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
                </select>
              </div>
              <div>
                <label className="text-[9px] font-bold tracking-[0.14em]" style={{ color: T.tenue }}>TELÉFONO</label>
                <input value={form.telefono} style={input}
                  onChange={e => setForm(f => ({ ...f, telefono: e.target.value }))} />
              </div>
            </div>
            <div>
              <label className="text-[9px] font-bold tracking-[0.14em]" style={{ color: T.tenue }}>
                CORREO DE CONTACTO
              </label>
              <input type="email" value={form.email_contacto} style={input}
                onChange={e => setForm(f => ({ ...f, email_contacto: e.target.value }))} />
            </div>

            <div className="rounded-lg p-3 space-y-2.5"
              style={{ backgroundColor: '#0a0d18', border: `1px solid ${T.bordeSuave}` }}>
              <p className="text-[9px] font-bold tracking-[0.14em]" style={{ color: T.acento }}>PRIMERA SUCURSAL</p>
              <div className="grid grid-cols-2 gap-3">
                <input required value={form.sucursal_nombre} placeholder="Nombre" style={input}
                  onChange={e => setForm(f => ({ ...f, sucursal_nombre: e.target.value }))} />
                <input value={form.sucursal_direccion} placeholder="Dirección" style={input}
                  onChange={e => setForm(f => ({ ...f, sucursal_direccion: e.target.value }))} />
              </div>
            </div>

            <div className="rounded-lg p-3 space-y-2.5"
              style={{ backgroundColor: '#0a0d18', border: `1px solid ${T.bordeSuave}` }}>
              <p className="text-[9px] font-bold tracking-[0.14em]" style={{ color: T.acento }}>DUEÑO DEL GIMNASIO</p>
              <input required value={form.admin_nombre} placeholder="Nombre completo" style={input}
                onChange={e => setForm(f => ({ ...f, admin_nombre: e.target.value }))} />
              <input required type="email" value={form.admin_email} placeholder="Correo" style={input}
                onChange={e => setForm(f => ({ ...f, admin_email: e.target.value }))} />
              <input required type="password" minLength={8} value={form.admin_password}
                placeholder="Contraseña (mín. 8)" style={input}
                onChange={e => setForm(f => ({ ...f, admin_password: e.target.value }))} />
            </div>

            <div className="flex gap-3 pt-1">
              <button type="button" onClick={() => setAlta(false)}
                className="flex-1 py-2.5 rounded-lg text-[11px] font-bold"
                style={{ border: `1px solid ${T.borde}`, color: T.tenue }}>
                Cancelar
              </button>
              <button type="submit" disabled={guardando}
                className="flex-1 py-2.5 rounded-lg text-[11px] font-bold disabled:opacity-50"
                style={{ backgroundColor: T.acentoFuerte, color: '#fff' }}>
                {guardando ? 'Creando…' : 'Crear gimnasio'}
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Entrar como: se pide motivo porque abre datos personales de socios ajenos
          y el backend lo guarda en la bitácora de soporte. */}
      {soporte && (
        <div className="fixed inset-0 z-50 flex overflow-y-auto p-4" style={{ backgroundColor: 'rgba(4,6,12,0.82)' }}>
          <div className="w-full max-w-md mx-auto my-auto rounded-xl p-5 space-y-3"
            style={{ backgroundColor: T.panel, border: `1px solid ${T.aviso}55` }}>
            <h2 className="text-sm font-bold">Entrar como {soporte.nombre}</h2>
            <p className="text-[10px] leading-relaxed" style={{ color: T.tenue }}>
              Vas a operar el sistema como {soporte.admin?.nombre ?? 'su admin'}, con
              acceso a los datos personales de sus socios. Queda registrado con tu
              nombre, la hora y tu IP.
            </p>
            <div>
              <label className="text-[9px] font-bold tracking-[0.14em]" style={{ color: T.tenue }}>MOTIVO *</label>
              <input autoFocus value={motivo} style={input}
                placeholder="Ej. no puede cobrar en el POS"
                onChange={e => setMotivo(e.target.value)} />
            </div>
            <div className="flex gap-3 pt-1">
              <button onClick={() => setSoporte(null)}
                className="flex-1 py-2.5 rounded-lg text-[11px] font-bold"
                style={{ border: `1px solid ${T.borde}`, color: T.tenue }}>
                Cancelar
              </button>
              <button onClick={entrar} disabled={soporteLoading || !motivo.trim()}
                className="flex-1 py-2.5 rounded-lg text-[11px] font-bold disabled:opacity-50"
                style={{ backgroundColor: T.aviso, color: '#0a0d18' }}>
                {soporteLoading ? 'Entrando…' : 'Entrar'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
