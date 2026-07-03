import { useEffect, useState } from 'react'
import api from '../api/axios'
import toast from 'react-hot-toast'

const CATEGORIAS = ['renta', 'nomina', 'equipo', 'servicios', 'mantenimiento', 'marketing', 'otro']
const EMPTY = { categoria: 'otro', descripcion: '', monto: '', fecha: '' }

const inputCls = 'w-full border border-gray-200 rounded-lg px-3 py-2 text-sm mt-1 focus:outline-none focus:ring-2 focus:ring-blue-700'

export default function Gastos() {
  const [data, setData]   = useState([])
  const [modal, setModal] = useState(false)
  const [form, setForm]   = useState(EMPTY)

  const load = () => api.get('/socios/gastos/').then(r => setData(r.data))
  useEffect(() => { load() }, [])

  const total = data.reduce((s, g) => s + parseFloat(g.monto || 0), 0)

  const save = async e => {
    e.preventDefault()
    try {
      await api.post('/socios/gastos/', form)
      toast.success('Gasto registrado')
      setModal(false)
      setForm(EMPTY)
      load()
    } catch { toast.error('Error al guardar') }
  }

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-gray-800">Gastos</h1>
          <p className="text-xs text-gray-400 mt-0.5">Total: <span className="font-bold text-red-600">${total.toFixed(2)}</span></p>
        </div>
        <button
          onClick={() => setModal(true)}
          className="bg-blue-800 hover:bg-blue-900 text-white text-xs font-semibold px-4 py-2.5 rounded-xl transition shadow-sm"
        >
          + Registrar gasto
        </button>
      </div>

      <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 text-gray-400 text-xs uppercase">
            <tr>
              <th className="px-4 py-3 text-left">Categoría</th>
              <th className="px-4 py-3 text-left">Descripción</th>
              <th className="px-4 py-3 text-left">Monto</th>
              <th className="px-4 py-3 text-left">Fecha</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {data.map(g => (
              <tr key={g.id} className="hover:bg-gray-50">
                <td className="px-4 py-3 capitalize text-gray-600">{g.categoria}</td>
                <td className="px-4 py-3 text-gray-500">{g.descripcion}</td>
                <td className="px-4 py-3 font-medium text-red-600">${parseFloat(g.monto).toFixed(2)}</td>
                <td className="px-4 py-3 text-gray-500">{g.fecha}</td>
              </tr>
            ))}
            {data.length === 0 && (
              <tr><td colSpan={4} className="px-4 py-8 text-center text-gray-400">Sin gastos</td></tr>
            )}
          </tbody>
        </table>
      </div>

      {modal && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
          <div className="bg-white rounded-2xl shadow-xl p-6 w-full max-w-sm overflow-hidden">
            <div className="h-1 bg-gradient-to-r from-blue-900 to-blue-500 -mx-6 -mt-6 mb-5" />
            <h2 className="text-sm font-bold text-gray-800 mb-4">Registrar gasto</h2>
            <form onSubmit={save} className="space-y-3">
              <div>
                <label className="text-[10px] font-semibold text-gray-400 uppercase tracking-wide">Categoría</label>
                <select value={form.categoria} onChange={e => setForm(f => ({ ...f, categoria: e.target.value }))} className={inputCls}>
                  {CATEGORIAS.map(c => <option key={c} value={c}>{c}</option>)}
                </select>
              </div>
              <div>
                <label className="text-[10px] font-semibold text-gray-400 uppercase tracking-wide">Descripción</label>
                <input required value={form.descripcion} onChange={e => setForm(f => ({ ...f, descripcion: e.target.value }))} className={inputCls} />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-[10px] font-semibold text-gray-400 uppercase tracking-wide">Monto</label>
                  <input required type="number" step="0.01" value={form.monto} onChange={e => setForm(f => ({ ...f, monto: e.target.value }))} className={inputCls} />
                </div>
                <div>
                  <label className="text-[10px] font-semibold text-gray-400 uppercase tracking-wide">Fecha</label>
                  <input required type="date" value={form.fecha} onChange={e => setForm(f => ({ ...f, fecha: e.target.value }))} className={inputCls} />
                </div>
              </div>
              <div className="flex gap-3 pt-2">
                <button type="button" onClick={() => setModal(false)}
                  className="flex-1 border border-gray-200 text-gray-600 text-xs py-2.5 rounded-xl hover:bg-gray-50 transition">
                  Cancelar
                </button>
                <button type="submit"
                  className="flex-1 bg-blue-800 hover:bg-blue-900 text-white text-xs py-2.5 rounded-xl transition">
                  Guardar
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
