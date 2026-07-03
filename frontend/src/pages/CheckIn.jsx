import { useState } from 'react'
import api from '../api/axios'
import toast from 'react-hot-toast'

export default function CheckIn() {
  const [token, setToken]       = useState('')
  const [sucursal, setSucursal] = useState('1')
  const [result, setResult]     = useState(null)
  const [loading, setLoading]   = useState(false)

  const check = async e => {
    e.preventDefault()
    setLoading(true)
    setResult(null)
    try {
      const { data } = await api.post('/accesos/checkin/', { token, sucursal_id: sucursal })
      setResult({ ok: true, ...data })
      toast.success('Acceso permitido')
    } catch (err) {
      const d = err.response?.data
      setResult({ ok: false, motivo: d?.motivo || 'Error' })
      toast.error('Acceso denegado')
    } finally {
      setLoading(false)
      setToken('')
    }
  }

  return (
    <div className="max-w-md mx-auto space-y-6">
      <div>
        <h1 className="text-xl font-bold text-gray-800">Check-In</h1>
        <p className="text-xs text-gray-400 mt-0.5">Validar acceso por código QR</p>
      </div>

      <form onSubmit={check} className="bg-white rounded-xl p-6 shadow-sm border border-gray-100 space-y-4">
        <div className="h-1 bg-gradient-to-r from-blue-900 to-blue-500 rounded -mx-6 -mt-6 mb-5" />
        <div>
          <label className="text-[10px] font-semibold text-gray-400 uppercase tracking-wide block mb-1">Token QR</label>
          <input
            autoFocus
            required
            value={token}
            onChange={e => setToken(e.target.value)}
            placeholder="Escanea o escribe el código..."
            className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-700"
          />
        </div>
        <div>
          <label className="text-[10px] font-semibold text-gray-400 uppercase tracking-wide block mb-1">Sucursal ID</label>
          <input
            value={sucursal}
            onChange={e => setSucursal(e.target.value)}
            className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-700"
          />
        </div>
        <button
          type="submit"
          disabled={loading}
          className="w-full bg-blue-800 hover:bg-blue-900 text-white font-semibold py-2.5 rounded-xl transition disabled:opacity-50 text-sm"
        >
          {loading ? 'Verificando...' : 'Verificar acceso'}
        </button>
      </form>

      {result && (
        <div className={`rounded-xl p-6 border ${result.ok ? 'bg-green-50 border-green-200' : 'bg-red-50 border-red-200'}`}>
          <div className="text-4xl text-center mb-3">{result.ok ? '✅' : '🚫'}</div>
          <p className={`text-xl font-bold text-center ${result.ok ? 'text-green-700' : 'text-red-700'}`}>
            {result.ok ? 'ACCESO PERMITIDO' : 'ACCESO DENEGADO'}
          </p>
          {result.ok ? (
            <div className="mt-4 space-y-1 text-sm text-green-800">
              <p><span className="font-medium">Socio:</span> {result.socio}</p>
              <p><span className="font-medium">Plan:</span> {result.plan}</p>
              <p><span className="font-medium">Vence:</span> {result.vence ?? 'Sin fecha límite'}</p>
            </div>
          ) : (
            <p className="mt-3 text-sm text-red-700 text-center">{result.motivo}</p>
          )}
        </div>
      )}
    </div>
  )
}
