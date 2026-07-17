import { useEffect, useState } from 'react'
import api from '../api/axios'
import toast from 'react-hot-toast'

const CARD_STYLE = { backgroundColor: '#161b22', border: '1px solid #21262d' }
const INPUT_STYLE = { backgroundColor: '#0d1117', border: '1px solid #21262d', color: '#fff' }

const TIPOS = ['resistencia', 'fisico', 'combinaciones', 'defensa', 'sparring']
const TIPO_LABEL = { resistencia: 'Resistencia', fisico: 'Físico', combinaciones: 'Combinaciones', defensa: 'Defensa', sparring: 'Sparring' }
const NIVELES = ['principiante', 'intermedio', 'avanzado', 'todos']
const NIVEL_LABEL = { principiante: 'Principiante', intermedio: 'Intermedio', avanzado: 'Avanzado', todos: 'Todos' }

const NIVEL_COLORS = {
  principiante: { bg: 'rgba(34,197,94,0.15)', color: '#22c55e' },
  intermedio:   { bg: 'rgba(59,130,246,0.15)', color: '#3b82f6' },
  avanzado:     { bg: 'rgba(168,85,247,0.15)', color: '#a855f7' },
  todos:        { bg: 'rgba(139,148,158,0.15)', color: '#8b949e' },
}

const EMPTY = { nombre: '', tipo: 'resistencia', profesor: '', hora_inicio: '', hora_fin: '', dias: '', cupo_max: 20, nivel: 'todos', descripcion: '' }

const inputCls = 'w-full rounded-lg px-3 py-2 text-sm mt-1 focus:outline-none'

export default function Clases() {
  const [clases, setClases] = useState([])
  const [modal, setModal] = useState(false)
  const [form, setForm] = useState(EMPTY)
  const [loading, setLoading] = useState(false)
  const [tipoFiltro, setTipoFiltro] = useState('todos')

  const load = () => api.get('/gyms/clases/').then(r => setClases(r.data)).catch(() => {})
  useEffect(() => { load() }, [])

  const save = async e => {
    e.preventDefault()
    setLoading(true)
    try {
      if (form.id) {
        await api.patch(`/gyms/clases/${form.id}/`, form)
        toast.success('Clase actualizada')
      } else {
        await api.post('/gyms/clases/', form)
        toast.success('Clase creada')
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

  const del = async (id) => {
    if (!confirm('¿Eliminar clase?')) return
    try {
      await api.delete(`/gyms/clases/${id}/`)
      toast.success('Clase eliminada')
      load()
    } catch {
      toast.error('Error al eliminar')
    }
  }

  const filtered = tipoFiltro === 'todos' ? clases : clases.filter(c => c.tipo === tipoFiltro)

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-xl font-black text-white uppercase tracking-wide">CLASES</h2>
          <p className="text-xs mt-0.5" style={{ color: '#8b949e' }}>{clases.length} clases programadas</p>
        </div>
        <button
          onClick={() => { setForm(EMPTY); setModal(true) }}
          className="flex items-center gap-2 px-4 py-2.5 rounded-lg text-xs font-bold transition-all"
          style={{ backgroundColor: '#22c55e', color: '#0d1117' }}
          onMouseEnter={e => e.currentTarget.style.backgroundColor = '#16a34a'}
          onMouseLeave={e => e.currentTarget.style.backgroundColor = '#22c55e'}
        >
          + Nueva Clase
        </button>
      </div>

      {/* Filtros tipo */}
      <div className="flex gap-2 flex-wrap">
        {['todos', ...TIPOS].map(t => (
          <button
            key={t}
            onClick={() => setTipoFiltro(t)}
            className="px-3 py-1.5 rounded-lg text-xs font-semibold transition-all capitalize"
            style={tipoFiltro === t
              ? { backgroundColor: '#22c55e', color: '#0d1117' }
              : { backgroundColor: '#161b22', color: '#8b949e', border: '1px solid #21262d' }
            }
          >
            {t === 'todos' ? 'Todos' : TIPO_LABEL[t]}
          </button>
        ))}
      </div>

      {/* Cards */}
      <div className="space-y-3">
        {filtered.length === 0 && (
          <div className="rounded-xl p-10 text-center text-xs" style={{ ...CARD_STYLE, color: '#3d444d' }}>
            Sin clases. Crea una con el botón de arriba.
          </div>
        )}
        {filtered.map(c => {
          const pct = Math.min(Math.round((c.inscritos / c.cupo_max) * 100), 100)
          const llena = pct >= 100
          const nc = NIVEL_COLORS[c.nivel] || NIVEL_COLORS.todos
          return (
            <div key={c.id} className="rounded-xl p-5" style={CARD_STYLE}>
              <div className="flex items-start justify-between gap-3 flex-wrap">
                <div className="flex items-start gap-4">
                  <div className="w-10 h-10 rounded-lg flex items-center justify-center shrink-0 mt-0.5" style={{ backgroundColor: 'rgba(34,197,94,0.1)' }}>
                    <svg className="w-5 h-5 text-[#22c55e]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                    </svg>
                  </div>
                  <div>
                    <div className="flex items-center gap-2 flex-wrap">
                      <h3 className="text-sm font-bold text-white">{c.nombre}</h3>
                      <span className="text-[10px] px-2 py-0.5 rounded font-semibold capitalize" style={{ backgroundColor: nc.bg, color: nc.color }}>
                        {NIVEL_LABEL[c.nivel]}
                      </span>
                      {llena && (
                        <span className="text-[10px] px-2 py-0.5 rounded font-semibold" style={{ backgroundColor: 'rgba(239,68,68,0.15)', color: '#ef4444' }}>
                          Llena
                        </span>
                      )}
                    </div>
                    <p className="text-xs mt-1" style={{ color: '#8b949e' }}>
                      {c.hora_inicio?.slice(0, 5)}–{c.hora_fin?.slice(0, 5)}
                      {c.profesor && <> · <span className="text-white">{c.profesor}</span></>}
                      {c.dias && <> · {c.dias}</>}
                    </p>
                    <p className="text-[10px] mt-0.5 capitalize font-medium" style={{ color: '#22c55e' }}>
                      {TIPO_LABEL[c.tipo] || c.tipo}
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <div className="text-right">
                    <p className="text-sm font-bold" style={{ color: llena ? '#ef4444' : '#22c55e' }}>{c.inscritos}/{c.cupo_max}</p>
                    <p className="text-[10px]" style={{ color: '#8b949e' }}>inscritos</p>
                  </div>
                  <button onClick={() => { setForm(c); setModal(true) }} style={{ color: '#8b949e' }} className="hover:text-white transition-colors">
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                    </svg>
                  </button>
                </div>
              </div>

              {/* Ocupación bar */}
              <div className="mt-4">
                <div className="w-full h-1 rounded-full" style={{ backgroundColor: '#21262d' }}>
                  <div className="h-1 rounded-full transition-all" style={{ width: `${pct}%`, backgroundColor: llena ? '#ef4444' : '#22c55e' }} />
                </div>
              </div>

              {c.descripcion && (
                <p className="text-xs mt-3 leading-relaxed" style={{ color: '#8b949e' }}>{c.descripcion}</p>
              )}
            </div>
          )
        })}
      </div>

      {/* Modal */}
      {modal && (
        <div className="fixed inset-0 flex items-center justify-center z-50 p-4" style={{ backgroundColor: 'rgba(0,0,0,0.7)' }}>
          <div className="rounded-2xl p-6 w-full max-w-lg max-h-[90vh] overflow-y-auto" style={CARD_STYLE}>
            <div className="flex items-center justify-between mb-5">
              <h2 className="text-sm font-bold text-white">{form.id ? 'Editar clase' : 'Nueva clase'}</h2>
              <button onClick={() => setModal(false)} style={{ color: '#8b949e' }} className="hover:text-white">
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" /></svg>
              </button>
            </div>
            <form onSubmit={save} className="space-y-3">
              <div>
                <label className="text-[10px] font-bold tracking-widest" style={{ color: '#8b949e' }}>NOMBRE</label>
                <input required value={form.nombre} onChange={e => setForm(f => ({ ...f, nombre: e.target.value }))} className={inputCls} style={INPUT_STYLE} />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-[10px] font-bold tracking-widest" style={{ color: '#8b949e' }}>TIPO</label>
                  <select required value={form.tipo} onChange={e => setForm(f => ({ ...f, tipo: e.target.value }))} className={inputCls} style={INPUT_STYLE}>
                    {TIPOS.map(t => <option key={t} value={t}>{TIPO_LABEL[t]}</option>)}
                  </select>
                </div>
                <div>
                  <label className="text-[10px] font-bold tracking-widest" style={{ color: '#8b949e' }}>NIVEL</label>
                  <select value={form.nivel} onChange={e => setForm(f => ({ ...f, nivel: e.target.value }))} className={inputCls} style={INPUT_STYLE}>
                    {NIVELES.map(n => <option key={n} value={n}>{NIVEL_LABEL[n]}</option>)}
                  </select>
                </div>
              </div>
              <div>
                <label className="text-[10px] font-bold tracking-widest" style={{ color: '#8b949e' }}>PROFESOR</label>
                <input required value={form.profesor} onChange={e => setForm(f => ({ ...f, profesor: e.target.value }))} className={inputCls} style={INPUT_STYLE} placeholder="Nombre del instructor" />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-[10px] font-bold tracking-widest" style={{ color: '#8b949e' }}>HORA INICIO</label>
                  <input type="time" required value={form.hora_inicio} onChange={e => setForm(f => ({ ...f, hora_inicio: e.target.value }))} className={inputCls} style={INPUT_STYLE} />
                </div>
                <div>
                  <label className="text-[10px] font-bold tracking-widest" style={{ color: '#8b949e' }}>HORA FIN</label>
                  <input type="time" required value={form.hora_fin} onChange={e => setForm(f => ({ ...f, hora_fin: e.target.value }))} className={inputCls} style={INPUT_STYLE} />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-[10px] font-bold tracking-widest" style={{ color: '#8b949e' }}>DÍAS</label>
                  <input value={form.dias} onChange={e => setForm(f => ({ ...f, dias: e.target.value }))} className={inputCls} style={INPUT_STYLE} placeholder="Lun, Mié, Vie" />
                </div>
                <div>
                  <label className="text-[10px] font-bold tracking-widest" style={{ color: '#8b949e' }}>CUPO MÁX.</label>
                  <input type="number" min={1} value={form.cupo_max} onChange={e => setForm(f => ({ ...f, cupo_max: parseInt(e.target.value) }))} className={inputCls} style={INPUT_STYLE} />
                </div>
              </div>
              <div>
                <label className="text-[10px] font-bold tracking-widest" style={{ color: '#8b949e' }}>DESCRIPCIÓN</label>
                <textarea rows={3} value={form.descripcion} onChange={e => setForm(f => ({ ...f, descripcion: e.target.value }))} className={`${inputCls} resize-none`} style={INPUT_STYLE} />
              </div>
              <div className="flex gap-3 pt-2">
                <button type="button" onClick={() => setModal(false)}
                  className="flex-1 py-2.5 rounded-lg text-xs font-semibold"
                  style={{ border: '1px solid #21262d', color: '#8b949e', backgroundColor: 'transparent' }}>
                  Cancelar
                </button>
                <button type="submit" disabled={loading}
                  className="flex-1 py-2.5 rounded-lg text-xs font-bold disabled:opacity-50"
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
