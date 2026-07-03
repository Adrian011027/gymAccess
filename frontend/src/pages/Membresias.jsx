import { useEffect, useState } from 'react'
import api from '../api/axios'

export default function Membresias() {
  const [data, setData] = useState([])
  useEffect(() => { api.get('/socios/membresias/').then(r => setData(r.data)) }, [])

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-xl font-bold text-gray-800">Membresías</h1>
        <p className="text-xs text-gray-400 mt-0.5">{data.length} registradas</p>
      </div>

      <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 text-gray-400 text-xs uppercase">
            <tr>
              <th className="px-4 py-3 text-left">Socio</th>
              <th className="px-4 py-3 text-left">Plan</th>
              <th className="px-4 py-3 text-left">Inicio</th>
              <th className="px-4 py-3 text-left">Fin</th>
              <th className="px-4 py-3 text-left">Estado</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {data.map(m => (
              <tr key={m.id} className="hover:bg-gray-50">
                <td className="px-4 py-3 font-medium text-gray-800">{m.socio_nombre}</td>
                <td className="px-4 py-3 text-gray-500">{m.plan_nombre}</td>
                <td className="px-4 py-3 text-gray-500">{m.fecha_inicio}</td>
                <td className="px-4 py-3 text-gray-500">{m.fecha_fin ?? '—'}</td>
                <td className="px-4 py-3">
                  <span className={`text-xs px-2 py-0.5 rounded-full ${
                    m.estado === 'activa'
                      ? 'bg-green-50 text-green-700'
                      : 'bg-gray-100 text-gray-500'
                  }`}>
                    {m.estado}
                  </span>
                </td>
              </tr>
            ))}
            {data.length === 0 && (
              <tr><td colSpan={5} className="px-4 py-8 text-center text-gray-400">Sin membresías</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
