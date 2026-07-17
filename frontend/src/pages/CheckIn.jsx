import { useEffect, useRef, useState } from 'react'
import api from '../api/axios'

const RESET_MS = 6000 // el resultado se limpia solo para el siguiente socio

export default function CheckIn() {
  const [token, setToken]           = useState('')
  const [sucursales, setSucursales] = useState([])
  const [sucursal, setSucursal]     = useState('')
  const [result, setResult]         = useState(null)
  const [loading, setLoading]       = useState(false)
  const [hora, setHora]             = useState(new Date())
  const inputRef = useRef(null)
  const resetTimer = useRef(null)

  useEffect(() => {
    api.get('/gyms/sucursales/')
      .then(r => {
        setSucursales(r.data)
        if (r.data.length) setSucursal(String(r.data[0].id))
      })
      .catch(() => {})
    const reloj = setInterval(() => setHora(new Date()), 1000)
    return () => {
      clearInterval(reloj)
      clearTimeout(resetTimer.current)
    }
  }, [])

  const limpiar = () => {
    setResult(null)
    inputRef.current?.focus()
  }

  const check = async e => {
    e.preventDefault()
    if (!token.trim()) return
    setLoading(true)
    clearTimeout(resetTimer.current)
    try {
      const { data } = await api.post('/accesos/checkin/', { token: token.trim(), sucursal_id: sucursal })
      setResult({ ok: true, ...data })
    } catch (err) {
      const d = err.response?.data
      setResult({
        ok: false,
        socio: d?.socio,
        motivo: d?.error || d?.motivo || 'Error de conexión',
      })
    } finally {
      setLoading(false)
      setToken('')
      inputRef.current?.focus()
      resetTimer.current = setTimeout(limpiar, RESET_MS)
    }
  }

  return (
    <div className="min-h-full flex flex-col items-center justify-center py-8">
      <div className="w-full max-w-xl space-y-6">

        {/* Encabezado con reloj */}
        <div className="text-center">
          <p className="text-4xl font-black text-white tabular-nums">
            {hora.toLocaleTimeString('es-MX', { hour: '2-digit', minute: '2-digit' })}
          </p>
          <h1 className="text-sm font-bold tracking-widest mt-1" style={{ color: '#22c55e' }}>
            CONTROL DE ACCESO
          </h1>
          <p className="text-xs mt-0.5" style={{ color: '#8b949e' }}>
            Escanea tu código o escríbelo y presiona Enter
          </p>
        </div>

        {/* Formulario */}
        <form
          onSubmit={check}
          className="rounded-2xl p-6 space-y-4"
          style={{ backgroundColor: '#161b22', border: '1px solid #21262d' }}
        >
          <input
            ref={inputRef}
            autoFocus
            value={token}
            onChange={e => setToken(e.target.value)}
            onBlur={() => setTimeout(() => {
              // recupera el foco (para el lector QR) solo si no se está usando otro control
              const el = document.activeElement
              if (!el || el === document.body) inputRef.current?.focus()
            }, 100)}
            placeholder="CÓDIGO DE ACCESO"
            autoComplete="off"
            className="w-full text-center text-2xl font-black tracking-widest rounded-xl px-4 py-5 outline-none text-white placeholder:text-[#3d444d]"
            style={{ backgroundColor: '#0d1117', border: '2px solid #21262d', caretColor: '#22c55e' }}
            onFocus={e => (e.target.style.borderColor = '#22c55e')}
          />
          <div className="flex items-center gap-3">
            <select
              value={sucursal}
              onChange={e => setSucursal(e.target.value)}
              className="flex-1 text-xs rounded-lg px-3 py-2.5 outline-none"
              style={{ backgroundColor: '#0d1117', border: '1px solid #21262d', color: '#8b949e' }}
            >
              {sucursales.length === 0 && <option value="">Sin sucursales</option>}
              {sucursales.map(s => (
                <option key={s.id} value={s.id}>{s.nombre}</option>
              ))}
            </select>
            <button
              type="submit"
              disabled={loading || !token.trim()}
              className="px-6 py-2.5 rounded-lg font-bold text-sm text-white transition-all disabled:opacity-40"
              style={{ backgroundColor: '#22c55e' }}
            >
              {loading ? 'Verificando…' : 'Verificar'}
            </button>
          </div>
        </form>

        {/* Resultado */}
        {result && (
          <div
            className="rounded-2xl p-8 text-center transition-all"
            style={{
              backgroundColor: result.ok ? 'rgba(34,197,94,0.08)' : 'rgba(239,68,68,0.08)',
              border: `2px solid ${result.ok ? '#22c55e' : '#ef4444'}`,
            }}
          >
            {result.foto ? (
              <img
                src={result.foto}
                alt=""
                className="w-24 h-24 rounded-full object-cover mx-auto mb-4"
                style={{ border: `3px solid ${result.ok ? '#22c55e' : '#ef4444'}` }}
              />
            ) : (
              <div className="text-6xl mb-3">{result.ok ? '✅' : '🚫'}</div>
            )}
            <p className="text-3xl font-black" style={{ color: result.ok ? '#22c55e' : '#ef4444' }}>
              {result.ok ? 'BIENVENIDO' : 'ACCESO DENEGADO'}
            </p>
            {result.socio && (
              <p className="text-xl font-bold text-white mt-2">{result.socio}</p>
            )}
            {result.ok ? (
              <div className="mt-3 text-sm space-y-1" style={{ color: '#8b949e' }}>
                <p>Plan: <span className="text-white font-semibold">{result.plan}</span></p>
                <p>Vence: <span className="text-white font-semibold">{result.vence ?? 'Sin fecha límite'}</span></p>
              </div>
            ) : (
              <p className="mt-3 text-sm font-semibold" style={{ color: '#ef4444' }}>{result.motivo}</p>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
