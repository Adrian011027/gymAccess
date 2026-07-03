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

  const load = () => api.get('/socios/').then(r => setSocios(r.data)).catch(() => {})
  useEffect(() => { load() }, [])

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
      <div className="flex items-center justify-between">
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

      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2 px-3 py-2 rounded-lg flex-1 max-w-md" style={CARD_STYLE}>
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
        <div className="flex gap-1">
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
        <table className="w-full text-sm">
          <thead style={{ borderBottom: '1px solid #21262d' }}>
            <tr>
              {['SOCIO', 'EDAD', 'PLAN', 'ANTIGÜEDAD', 'F. NACIMIENTO', 'PRÓX. PAGO', 'ESTADO', ''].map(h => (
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
                    <button onClick={() => { setForm(s); setModal(true) }} style={{ color: '#8b949e' }} className="hover:text-white transition-colors">
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                      </svg>
                    </button>
                  </td>
                </tr>
              )
            })}
            {filtered.length === 0 && (
              <tr><td colSpan={8} className="px-4 py-10 text-center text-xs" style={{ color: '#3d444d' }}>Sin socios</td></tr>
            )}
          </tbody>
        </table>
      </div>

      {modal && (
        <div className="fixed inset-0 flex items-center justify-center z-50" style={{ backgroundColor: 'rgba(0,0,0,0.7)' }}>
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
