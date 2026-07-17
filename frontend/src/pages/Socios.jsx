import { useEffect, useState } from 'react'
import api from '../api/axios'
import toast from 'react-hot-toast'

const CARD_STYLE = { backgroundColor: '#161b22', border: '1px solid #21262d' }
const INPUT_STYLE = { backgroundColor: '#0d1117', border: '1px solid #21262d', color: '#fff' }

const EMPTY = { nombre: '', apellido: '', email: '', telefono: '', sexo: '', fecha_nacimiento: '' }

const AVATAR_COLORS = ['#f97316', '#a855f7', '#3b82f6', '#22c55e', '#ef4444', '#eab308', '#06b6d4']
function avatarColor(name) { return AVATAR_COLORS[(name?.charCodeAt(0) || 0) % AVATAR_COLORS.length] }
function initials(n = '', a = '') { return `${n[0] || ''}${a[0] || ''}`.toUpperCase() }

function edad(fechaNac) {
  if (!fechaNac) return '—'
  const d = new Date(fechaNac)
  const hoy = new Date()
  let y = hoy.getFullYear() - d.getFullYear()
  if (hoy < new Date(hoy.getFullYear(), d.getMonth(), d.getDate())) y--
  return y
}

function antiguedad(creadoEn) {
  if (!creadoEn) return '—'
  const d = new Date(creadoEn)
  const hoy = new Date()
  const meses = (hoy.getFullYear() - d.getFullYear()) * 12 + (hoy.getMonth() - d.getMonth())
  const y = Math.floor(meses / 12)
  const m = meses % 12
  return `${y}a ${m}m`
}

const PLAN_COLORS = {
  'Socio Regular': { bg: 'rgba(34,197,94,0.15)', color: '#22c55e' },
}
function planBadge(nombre) {
  const c = PLAN_COLORS[nombre] || { bg: 'rgba(139,148,158,0.15)', color: '#8b949e' }
  return c
}

export default function Socios() {
  const [socios, setSocios] = useState([])
  const [modal, setModal] = useState(false)
  const [form, setForm] = useState(EMPTY)
  const [search, setSearch] = useState('')
  const [filtro, setFiltro] = useState('todos')
  const [loading, setLoading] = useState(false)
  const [huellaModal, setHuellaModal] = useState(null)
  const [huellaEstado, setHuellaEstado] = useState('idle') // idle | esperando | ok | error
  const [huellaMsg, setHuellaMsg] = useState('')

  const load = () => api.get('/socios/').then(r => setSocios(r.data)).catch(() => {})
  useEffect(() => { load() }, [])

  const abrirSincronizarHuella = socio => {
    setHuellaModal(socio)
    setHuellaEstado('idle')
    setHuellaMsg('')
  }

  // El agente local (SDK DigitalPersona U.are.U 4500) expone window.fingerprintAgent
  // cuando corre en la PC de la sucursal; en su ausencia, solo se muestra el estado del backend.
  const capturarHuella = async () => {
    if (!huellaModal) return
    setHuellaEstado('esperando')
    setHuellaMsg('Coloca el dedo en el lector...')
    try {
      if (!window.fingerprintAgent?.capturar) {
        throw new Error('Agente de huella no detectado en esta PC')
      }
      const template = await window.fingerprintAgent.capturar()
      const { data } = await api.post('/accesos/sincronizar-huella/', {
        socio_id: huellaModal.id,
        template,
      })
      setHuellaEstado('ok')
      setHuellaMsg('Huella sincronizada correctamente')
      toast.success(`Huella registrada para ${huellaModal.nombre}`)
    } catch (err) {
      setHuellaEstado('error')
      setHuellaMsg(err.response?.data?.error || err.message || 'Error al capturar huella')
    }
  }

  const save = async e => {
    e.preventDefault()
    setLoading(true)
    try {
      if (form.id) {
        await api.patch(`/socios/${form.id}/`, form)
        toast.success('Socio actualizado')
      } else {
        await api.post('/socios/', form)
        toast.success('Socio registrado')
      }
      setModal(false)
      setForm(EMPTY)
      load()
    } catch {
      toast.error('Error al guardar')
    } finally {
      setLoading(false)
    }
  }

  const activos = socios.filter(s => s.activo).length
  const inactivos = socios.filter(s => !s.activo).length

  const filtered = socios
    .filter(s => filtro === 'activos' ? s.activo : filtro === 'inactivos' ? !s.activo : true)
    .filter(s => `${s.nombre} ${s.apellido} ${s.email}`.toLowerCase().includes(search.toLowerCase()))

  const inputCls = 'w-full rounded-lg px-3 py-2 text-sm mt-1 focus:outline-none text-white'

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-xl font-black text-white uppercase tracking-wide">SOCIOS</h2>
          <p className="text-xs mt-0.5" style={{ color: '#8b949e' }}>{activos} activos · {inactivos} inactivos</p>
        </div>
        <button
          onClick={() => { setForm(EMPTY); setModal(true) }}
          className="flex items-center gap-2 px-4 py-2.5 rounded-lg text-xs font-bold text-white transition-all"
          style={{ backgroundColor: '#22c55e', color: '#0d1117' }}
          onMouseEnter={e => e.currentTarget.style.backgroundColor = '#16a34a'}
          onMouseLeave={e => e.currentTarget.style.backgroundColor = '#22c55e'}
        >
          + Nuevo Socio
        </button>
      </div>

      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div className="flex items-center gap-2 px-3 py-2 rounded-lg flex-1 sm:max-w-md" style={CARD_STYLE}>
          <svg className="w-4 h-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" style={{ color: '#8b949e' }}>
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
          <input
            type="text"
            placeholder="Buscar por nombre..."
            value={search}
            onChange={e => setSearch(e.target.value)}
            className="bg-transparent text-sm w-full outline-none text-white placeholder:text-[#3d444d]"
          />
        </div>
        <div className="flex gap-1 flex-wrap">
          {[['todos', 'Todos'], ['activos', 'Activos'], ['inactivos', 'Inactivos']].map(([v, l]) => (
            <button
              key={v}
              onClick={() => setFiltro(v)}
              className="px-4 py-2 rounded-lg text-xs font-semibold transition-all"
              style={filtro === v
                ? { backgroundColor: '#22c55e', color: '#0d1117' }
                : { backgroundColor: '#161b22', color: '#8b949e', border: '1px solid #21262d' }
              }
            >{l}</button>
          ))}
        </div>
      </div>

      <div className="rounded-xl overflow-hidden" style={CARD_STYLE}>
        <div className="overflow-x-auto">
        <table className="w-full text-sm min-w-[920px]">
          <thead style={{ borderBottom: '1px solid #21262d' }}>
            <tr>
              {['SOCIO', 'CÓDIGO', 'EDAD', 'PLAN', 'ANTIGÜEDAD', 'F. NACIMIENTO', 'PRÓX. PAGO', 'ESTADO', ''].map(h => (
                <th key={h} className="px-4 py-3 text-left text-[10px] font-bold tracking-widest" style={{ color: '#8b949e' }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {filtered.map((s, i) => {
              const plan = s.membresia_activa?.plan
              const pc = planBadge(plan)
              const vence = s.membresia_activa?.fecha_fin
              const venceHoy = vence && new Date(vence).toDateString() === new Date().toDateString()
              return (
                <tr key={s.id} style={{ borderBottom: i < filtered.length - 1 ? '1px solid #21262d' : undefined }}>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 rounded-full flex items-center justify-center text-[10px] font-bold shrink-0"
                        style={{ backgroundColor: avatarColor(s.nombre), color: '#0d1117' }}>
                        {initials(s.nombre, s.apellido)}
                      </div>
                      <span className="text-xs font-semibold text-white">{s.nombre} {s.apellido}</span>
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    {s.codigo_acceso ? (
                      <button
                        onClick={() => { navigator.clipboard.writeText(s.codigo_acceso); toast.success('Código copiado') }}
                        title="Clic para copiar"
                        className="text-[10px] font-mono px-2 py-1 rounded transition-opacity hover:opacity-70"
                        style={{ backgroundColor: 'rgba(34,197,94,0.08)', color: '#22c55e', border: '1px solid rgba(34,197,94,0.25)' }}
                      >
                        {s.codigo_acceso}
                      </button>
                    ) : (
                      <span className="text-[10px]" style={{ color: '#3d444d' }}>Sin código</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-xs" style={{ color: '#8b949e' }}>{edad(s.fecha_nacimiento)}</td>
                  <td className="px-4 py-3">
                    {plan
                      ? <span className="text-[10px] px-2 py-0.5 rounded font-semibold" style={{ backgroundColor: pc.bg, color: pc.color }}>{plan}</span>
                      : <span className="text-[10px]" style={{ color: '#3d444d' }}>Sin plan</span>
                    }
                  </td>
                  <td className="px-4 py-3 text-xs" style={{ color: '#8b949e' }}>{antiguedad(s.creado_en)}</td>
                  <td className="px-4 py-3 text-xs" style={{ color: '#8b949e' }}>{s.fecha_nacimiento || '—'}</td>
                  <td className="px-4 py-3 text-xs font-semibold" style={{ color: vencePronto(vence) ? '#f97316' : '#8b949e' }}>
                    {vence || '—'}
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-1.5">
                      <span className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: s.activo ? '#22c55e' : '#ef4444' }} />
                      <span className="text-[10px] font-semibold" style={{ color: s.activo ? '#22c55e' : '#ef4444' }}>
                        {s.activo ? 'Activo' : 'Inactivo'}
                      </span>
                    </div>
                  </td>
                  <td className="px-4 py-3 text-right">
                    <div className="flex items-center justify-end gap-3">
                      <button onClick={() => abrirSincronizarHuella(s)} title="Sincronizar huella" style={{ color: '#8b949e' }} className="hover:text-white transition-colors">
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 11c1.5 0 2 1 2 2.5S13 17 12 17s-2-1-2-2.5.5-3.5 2-3.5zm0-7a7 7 0 00-7 7c0 1.5.5 3 2 4.5M12 4a7 7 0 017 7c0 3-1 5-3 7M9 8.5a3 3 0 016 0c0 .5-.1 1-.3 1.5" />
                        </svg>
                      </button>
                      <button onClick={() => { setForm(s); setModal(true) }} style={{ color: '#8b949e' }} className="hover:text-white transition-colors">
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                        </svg>
                      </button>
                    </div>
                  </td>
                </tr>
              )
            })}
            {filtered.length === 0 && (
              <tr><td colSpan={9} className="px-4 py-10 text-center text-xs" style={{ color: '#3d444d' }}>Sin socios</td></tr>
            )}
          </tbody>
        </table>
        </div>
      </div>

      {modal && (
        <div className="fixed inset-0 flex items-center justify-center z-50 p-4" style={{ backgroundColor: 'rgba(0,0,0,0.7)' }}>
          <div className="rounded-2xl p-6 w-full max-w-md" style={CARD_STYLE}>
            <div className="flex items-center justify-between mb-5">
              <h2 className="text-sm font-bold text-white">{form.id ? 'Editar socio' : 'Nuevo socio'}</h2>
              <button onClick={() => setModal(false)} style={{ color: '#8b949e' }} className="hover:text-white">
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" /></svg>
              </button>
            </div>
            <form onSubmit={save} className="space-y-3">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-[10px] font-bold tracking-widest" style={{ color: '#8b949e' }}>NOMBRE</label>
                  <input required value={form.nombre} onChange={e => setForm(f => ({ ...f, nombre: e.target.value }))} className={inputCls} style={INPUT_STYLE} />
                </div>
                <div>
                  <label className="text-[10px] font-bold tracking-widest" style={{ color: '#8b949e' }}>APELLIDO</label>
                  <input required value={form.apellido} onChange={e => setForm(f => ({ ...f, apellido: e.target.value }))} className={inputCls} style={INPUT_STYLE} />
                </div>
              </div>
              <div>
                <label className="text-[10px] font-bold tracking-widest" style={{ color: '#8b949e' }}>EMAIL</label>
                <input type="email" value={form.email} onChange={e => setForm(f => ({ ...f, email: e.target.value }))} className={inputCls} style={INPUT_STYLE} />
              </div>
              <div>
                <label className="text-[10px] font-bold tracking-widest" style={{ color: '#8b949e' }}>TELÉFONO</label>
                <input value={form.telefono} onChange={e => setForm(f => ({ ...f, telefono: e.target.value }))} className={inputCls} style={INPUT_STYLE} />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-[10px] font-bold tracking-widest" style={{ color: '#8b949e' }}>SEXO</label>
                  <select value={form.sexo} onChange={e => setForm(f => ({ ...f, sexo: e.target.value }))} className={inputCls} style={INPUT_STYLE}>
                    <option value="">—</option>
                    <option value="M">Masculino</option>
                    <option value="F">Femenino</option>
                    <option value="O">Otro</option>
                  </select>
                </div>
                <div>
                  <label className="text-[10px] font-bold tracking-widest" style={{ color: '#8b949e' }}>FECHA NACIMIENTO</label>
                  <input type="date" value={form.fecha_nacimiento || ''} onChange={e => setForm(f => ({ ...f, fecha_nacimiento: e.target.value }))} className={inputCls} style={INPUT_STYLE} />
                </div>
              </div>
              <div className="flex gap-3 pt-2">
                <button type="button" onClick={() => setModal(false)}
                  className="flex-1 py-2.5 rounded-lg text-xs font-semibold transition-colors"
                  style={{ border: '1px solid #21262d', color: '#8b949e', backgroundColor: 'transparent' }}>
                  Cancelar
                </button>
                <button type="submit" disabled={loading}
                  className="flex-1 py-2.5 rounded-lg text-xs font-bold transition-all disabled:opacity-50"
                  style={{ backgroundColor: '#22c55e', color: '#0d1117' }}>
                  {loading ? 'Guardando...' : 'Guardar'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {huellaModal && (
        <div className="fixed inset-0 flex items-center justify-center z-50" style={{ backgroundColor: 'rgba(0,0,0,0.7)' }}>
          <div className="rounded-2xl p-6 w-full max-w-sm text-center" style={CARD_STYLE}>
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-sm font-bold text-white">Sincronizar huella</h2>
              <button onClick={() => setHuellaModal(null)} style={{ color: '#8b949e' }} className="hover:text-white">
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" /></svg>
              </button>
            </div>

            <p className="text-xs mb-4" style={{ color: '#8b949e' }}>
              {huellaModal.nombre} {huellaModal.apellido}
            </p>

            <div className="flex items-center justify-center mb-4">
              <div className="w-20 h-20 rounded-full flex items-center justify-center"
                style={{
                  backgroundColor: huellaEstado === 'ok' ? 'rgba(34,197,94,0.15)' : huellaEstado === 'error' ? 'rgba(239,68,68,0.15)' : 'rgba(139,148,158,0.1)',
                }}>
                <svg className="w-9 h-9" fill="none" stroke="currentColor" viewBox="0 0 24 24"
                  style={{ color: huellaEstado === 'ok' ? '#22c55e' : huellaEstado === 'error' ? '#ef4444' : '#8b949e' }}>
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 11c1.5 0 2 1 2 2.5S13 17 12 17s-2-1-2-2.5.5-3.5 2-3.5zm0-7a7 7 0 00-7 7c0 1.5.5 3 2 4.5M12 4a7 7 0 017 7c0 3-1 5-3 7M9 8.5a3 3 0 016 0c0 .5-.1 1-.3 1.5" />
                </svg>
              </div>
            </div>

            <p className="text-xs mb-5 min-h-[1rem]" style={{ color: huellaEstado === 'error' ? '#ef4444' : huellaEstado === 'ok' ? '#22c55e' : '#8b949e' }}>
              {huellaMsg || 'Coloca el dedo en el lector cuando estés listo'}
            </p>

            <button
              onClick={capturarHuella}
              disabled={huellaEstado === 'esperando'}
              className="w-full py-2.5 rounded-lg text-xs font-bold transition-all disabled:opacity-50"
              style={{ backgroundColor: '#22c55e', color: '#0d1117' }}
            >
              {huellaEstado === 'esperando' ? 'Leyendo...' : 'Capturar huella'}
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

function vencePronto(fecha) {
  if (!fecha) return false
  const d = new Date(fecha)
  const hoy = new Date()
  const diff = (d - hoy) / (1000 * 60 * 60 * 24)
  return diff <= 3
}
