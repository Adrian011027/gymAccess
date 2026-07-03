import { useEffect, useState } from 'react'
import api from '../api/axios'

export default function Accesos() {
  const [accesos, setAccesos] = useState([])
  useEffect(() => { api.get('/accesos/').then(r => setAccesos(r.data)) }, [])

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-xl font-bold text-gray-800">Accesos</h1>
        <p className="text-xs text-gray-400 mt-0.5">Historial de entradas</p>
      </div>

      <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 text-gray-400 text-xs uppercase">
            <tr>
              <th className="px-4 py-3 text-left">Socio</th>
              <th className="px-4 py-3 text-left">Sucursal</th>
              <th className="px-4 py-3 text-left">Método</th>
              <th className="px-4 py-3 text-left">Resultado</th>
              <th className="px-4 py-3 text-left">Fecha / Hora</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {accesos.map(a => (
              <tr key={a.id} className="hover:bg-gray-50">
                <td className="px-4 py-3 font-medium text-gray-800">{a.socio_nombre}</td>
                <td className="px-4 py-3 text-gray-500">{a.sucursal_nombre}</td>
                <td className="px-4 py-3 text-gray-500 capitalize">{a.metodo_usado}</td>
                <td className="px-4 py-3">
                  <span className={`text-xs px-2 py-0.5 rounded-full ${
                    a.resultado === 'permitido'
                      ? 'bg-green-50 text-green-700'
                      : 'bg-red-50 text-red-600'
                  }`}>
                    {a.resultado}
                  </span>
                </td>
                <td className="px-4 py-3 text-gray-500 text-xs">{new Date(a.timestamp).toLocaleString('es-MX')}</td>
              </tr>
            ))}
            {accesos.length === 0 && (
              <tr><td colSpan={5} className="px-4 py-8 text-center text-gray-400">Sin accesos registrados</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
