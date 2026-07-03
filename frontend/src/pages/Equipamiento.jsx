import { useEffect, useState } from 'react'
import api from '../api/axios'
import toast from 'react-hot-toast'

const CARD_STYLE = { backgroundColor: '#161b22', border: '1px solid #21262d' }
const INPUT_STYLE = { backgroundColor: '#0d1117', border: '1px solid #21262d', color: '#fff' }

const CATEGORIAS = ['impacto', 'infraestructura', 'proteccion', 'cardio', 'piso', 'pesas']
const CAT_LABEL = {
  impacto: 'Impacto', infraestructura: 'Infraestructura', proteccion: 'Protección',
  cardio: 'Cardio', piso: 'Piso', pesas: 'Pesas',
}

const EMPTY = { nombre: '', categoria: 'impacto', cantidad: 1, ultima_revision: '', ubicacion: '' }
const inputCls = 'w-full rounded-lg px-3 py-2 text-sm mt-1 focus:outline-none'

export default function Equipamiento() {
  const [items, setItems] = useState([])
  const [modal, setModal] = useState(false)
  const [form, setForm] = useState(EMPTY)
  const [loading, setLoading] = useState(false)
  const [catFiltro, setCatFiltro] = useState('todos')

  const load = () => api.get('/gyms/equipamiento/').then(r => setItems(r.data)).catch(() => {})
  useEffect(() => { load() }, [])

  const save = async e => {
    e.preventDefault()
    setLoading(true)
    try {
      if (form.id) {
        await api.patch(`/gyms/equipamiento/${form.id}/`, form)
        toast.success('Ítem actualizado')
      } else {
        await api.post('/gyms/equipamiento/', form)
        toast.success('Ítem añadido')
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

  const filtered = catFiltro === 'todos' ? items : items.filter(i => i.categoria === catFiltro)
  const total = items.reduce((s, i) => s + i.cantidad, 0)

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-black text-white uppercase tracking-wide">EQUIPAMIENTO</h2>
          <p className="text-xs mt-0.5" style={{ color: '#8b949e' }}>{total} ítems en inventario</p>
        </div>
        <button
          onClick={() => { setForm(EMPTY); setModal(true) }}
          className="flex items-center gap-2 px-4 py-2.5 rounded-lg text-xs font-bold transition-all"
          style={{ backgroundColor: '#22c55e', color: '#0d1117' }}
          onMouseEnter={e => e.currentTarget.style.backgroundColor = '#16a34a'}
          onMouseLeave={e => e.currentTarget.style.backgroundColor = '#22c55e'}
        >
          + Añadir Ítem
        </button>
      </div>

      {/* Filtros */}
      <div className="flex gap-2 flex-wrap">
        {['todos', ...CATEGORIAS].map(c => (
          <button
            key={c}
            onClick={() => setCatFiltro(c)}
            className="px-3 py-1.5 rounded-lg text-xs font-semibold transition-all capitalize"
            style={catFiltro === c
              ? { backgroundColor: '#22c55e', color: '#0d1117' }
              : { backgroundColor: '#161b22', color: '#8b949e', border: '1px solid #21262d' }
            }
          >
            {c === 'todos' ? 'Todos' : CAT_LABEL[c]}
          </button>
        ))}
      </div>

      {/* Table */}
      <div className="rounded-xl overflow-hidden" style={CARD_STYLE}>
        <table className="w-full text-sm">
          <thead style={{ borderBottom: '1px solid #21262d' }}>
            <tr>
              {['ÍTEM', 'CATEGORÍA', 'CANTIDAD', 'ÚLTIMA REVISIÓN', 'UBICACIÓN', ''].map(h => (
                <th key={h} className="px-4 py-3 text-left text-[10px] font-bold tracking-widest" style={{ color: '#8b949e' }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {filtered.map((item, i) => (
              <tr key={item.id} style={{ borderBottom: i < filtered.length - 1 ? '1px solid #21262d' : undefined }}>
                <td className="px-4 py-3 text-xs font-semibold text-white">{item.nombre}</td>
                <td className="px-4 py-3 text-xs capitalize" style={{ color: '#8b949e' }}>{CAT_LABEL[item.categoria] || item.categoria}</td>
                <td className="px-4 py-3 text-xs font-bold text-white">{item.cantidad}</td>
                <td className="px-4 py-3 text-xs" style={{ color: '#8b949e' }}>{item.ultima_revision || '—'}</td>
                <td className="px-4 py-3 text-xs" style={{ color: '#8b949e' }}>{item.ubicacion || '—'}</td>
                <td className="px-4 py-3 text-right">
                  <button onClick={() => { setForm(item); setModal(true) }} style={{ color: '#8b949e' }} className="hover:text-white transition-colors">
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                    </svg>
                  </button>
                </td>
              </tr>
            ))}
            {filtered.length === 0 && (
              <tr><td colSpan={6} className="px-4 py-10 text-center text-xs" style={{ color: '#3d444d' }}>Sin ítems</td></tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Modal */}
      {modal && (
        <div className="fixed inset-0 flex items-center justify-center z-50" style={{ backgroundColor: 'rgba(0,0,0,0.7)' }}>
          <div className="rounded-2xl p-6 w-full max-w-md" style={CARD_STYLE}>
            <div className="flex items-center justify-between mb-5">
              <h2 className="text-sm font-bold text-white">{form.id ? 'Editar ítem' : 'Añadir ítem'}</h2>
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
                  <label className="text-[10px] font-bold tracking-widest" style={{ color: '#8b949e' }}>CATEGORÍA</label>
                  <select value={form.categoria} onChange={e => setForm(f => ({ ...f, categoria: e.target.value }))} className={inputCls} style={INPUT_STYLE}>
                    {CATEGORIAS.map(c => <option key={c} value={c}>{CAT_LABEL[c]}</option>)}
                  </select>
                </div>
                <div>
                  <label className="text-[10px] font-bold tracking-widest" style={{ color: '#8b949e' }}>CANTIDAD</label>
                  <input type="number" min={0} value={form.cantidad} onChange={e => setForm(f => ({ ...f, cantidad: parseInt(e.target.value) }))} className={inputCls} style={INPUT_STYLE} />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-[10px] font-bold tracking-widest" style={{ color: '#8b949e' }}>ÚLTIMA REVISIÓN</label>
                  <input type="date" value={form.ultima_revision || ''} onChange={e => setForm(f => ({ ...f, ultima_revision: e.target.value }))} className={inputCls} style={INPUT_STYLE} />
                </div>
                <div>
                  <label className="text-[10px] font-bold tracking-widest" style={{ color: '#8b949e' }}>UBICACIÓN</label>
                  <input value={form.ubicacion} onChange={e => setForm(f => ({ ...f, ubicacion: e.target.value }))} className={inputCls} style={INPUT_STYLE} placeholder="Ej: Sala Principal" />
                </div>
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
