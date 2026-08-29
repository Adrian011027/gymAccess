import { useEffect, useRef, useState } from 'react'
import api from '../api/axios'
import { useAuth } from '../context/AuthContext'

const RESET_MS = 6000 // el resultado se limpia solo para el siguiente socio

// En pantallas táctiles no se fuerza el foco: abriría el teclado en cada scan y taparía el resultado
const esTactil = window.matchMedia('(pointer: coarse)').matches

export default function CheckIn() {
  const { sucursalId, verTodasLasSucursales } = useAuth()
  const [token, setToken]           = useState('')
  const [sucursales, setSucursales] = useState([])
  const [sucursal, setSucursal]     = useState('')
  const [result, setResult]         = useState(null)
  const [loading, setLoading]       = useState(false)
  const [hora, setHora]             = useState(new Date())
  // Visita de otra sucursal esperando que el dueño teclee su contraseña.
  const [visita, setVisita]         = useState(null)
  const [visitaError, setVisitaError] = useState('')
  // Búsqueda por nombre para el socio que llegó sin su código.
  const [busqueda, setBusqueda] = useState('')
  const [candidatos, setCandidatos] = useState(null)
  const [buscando, setBuscando] = useState(false)
  const inputRef = useRef(null)
  const resetTimer = useRef(null)

  useEffect(() => {
    api.get('/gyms/sucursales/')
      .then(r => {
        setSucursales(r.data)
        // Recepción está atada a su sucursal; no elige.
        const propia = r.data.find(s => s.id === sucursalId)
        if (propia) setSucursal(String(propia.id))
        else if (r.data.length) setSucursal(String(r.data[0].id))
      })
      .catch(() => {})
    const reloj = setInterval(() => setHora(new Date()), 1000)
    return () => {
      clearInterval(reloj)
      clearTimeout(resetTimer.current)
    }
  }, [sucursalId])

  const limpiar = () => {
    setResult(null)
    setVisita(null)
    setVisitaError('')
    setBusqueda('')
    setCandidatos(null)
    if (!esTactil) inputRef.current?.focus()
  }

  const buscarPorNombre = async e => {
    e.preventDefault()
    const q = busqueda.trim()
    if (q.length < 2) return
    setBuscando(true)
    try {
      const { data } = await api.get('/accesos/buscar-socio/', { params: { q } })
      setCandidatos(data)
    } catch {
      setCandidatos([])
    } finally {
      setBuscando(false)
    }
  }

  const enviar = async (codigo, extra) => {
    const { data } = await api.post('/accesos/checkin/', {
      token: codigo, sucursal_id: sucursal, ...extra,
    })
    return data
  }

  const check = async e => {
    e.preventDefault()
    if (!token.trim()) return
    procesar(token.trim())
  }

  // El acceso siempre se registra con el token del QR, venga de un escaneo o de la
  // búsqueda por nombre: una sola puerta, con las mismas reglas de sucursal y vigencia.
  const procesar = async codigo => {
    setCandidatos(null)
    setBusqueda('')
    setLoading(true)
    clearTimeout(resetTimer.current)
    try {
      setResult({ ok: true, ...(await enviar(codigo)) })
    } catch (err) {
      const d = err.response?.data
      // Socio de otra sucursal con política de autorización: en vez de cerrar el caso,
      // se deja abierto para que el dueño decida sin volver a escanear.
      if (d?.requiere_autorizacion) {
        setVisita({ token: codigo, socio: d.socio, sucursal_socio: d.sucursal_socio })
        setLoading(false)
        return
      }
      setResult({
        ok: false,
        socio: d?.socio,
        motivo: d?.error || d?.motivo || 'Error de conexión',
        sucursal_socio: d?.sucursal_socio,
      })
    } finally {
      setLoading(false)
      setToken('')
      if (!esTactil) inputRef.current?.focus()
      if (!visita) resetTimer.current = setTimeout(limpiar, RESET_MS)
    }
  }

  // Un clic autoriza la visita: no se pide contraseña, el respaldo es la bitácora
  // (el acceso queda con `autorizado_por` = quien pulsó).
  const autorizarVisita = async () => {
    setLoading(true)
    setVisitaError('')
    try {
      const data = await enviar(visita.token, { autorizar: true })
      setVisita(null)
      setResult({ ok: true, ...data })
      resetTimer.current = setTimeout(limpiar, RESET_MS)
    } catch {
      setVisitaError('No se pudo autorizar el acceso.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-full flex flex-col items-center justify-center py-4 sm:py-8">
      <div className="w-full max-w-xl space-y-4 sm:space-y-6">

        {/* Encabezado con reloj */}
        <div className="text-center">
          <p className="text-3xl sm:text-4xl font-black text-white tabular-nums">
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
          className="rounded-2xl p-4 sm:p-6 space-y-4"
          style={{ backgroundColor: '#161b22', border: '1px solid #21262d' }}
        >
          <input
            ref={inputRef}
            autoFocus={!esTactil}
            value={token}
            onChange={e => setToken(e.target.value)}
            onBlur={() => setTimeout(() => {
              // recupera el foco (para el lector QR) solo si no se está usando otro control
              if (esTactil) return
              const el = document.activeElement
              if (!el || el === document.body) inputRef.current?.focus()
            }, 100)}
            placeholder="ESCANEA EL QR O TECLEA EL N° DE SOCIO"
            autoComplete="off"
            className="w-full text-center text-lg sm:text-2xl font-black tracking-widest rounded-xl px-4 py-4 sm:py-5 outline-none text-white placeholder:text-[#3d444d]"
            style={{ backgroundColor: '#0d1117', border: '2px solid #21262d', caretColor: '#22c55e' }}
            onFocus={e => (e.target.style.borderColor = '#22c55e')}
          />
          {/* El campo aceptaba solo el token del QR y no había nada en pantalla que
              dijera que el número corto también sirve, así que recepción seguía
              buscando por nombre al socio que llegaba sin teléfono. */}
          <p className="text-[10px] text-center -mt-1" style={{ color: '#3d444d' }}>
            Acepta el código del QR o el número de socio (1001, 1002…)
          </p>
          <div className="flex flex-col sm:flex-row sm:items-center gap-3">
            {verTodasLasSucursales ? (
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
            ) : (
              // Recepción no elige puerta: registra en la suya.
              <div
                className="flex-1 text-xs rounded-lg px-3 py-2.5"
                style={{ backgroundColor: '#0d1117', border: '1px solid #21262d', color: '#8b949e' }}
              >
                Sucursal:{' '}
                <span className="text-white font-semibold">
                  {sucursales.find(s => String(s.id) === String(sucursal))?.nombre || '—'}
                </span>
              </div>
            )}
            <button
              type="submit"
              disabled={loading || !token.trim()}
              className="w-full sm:w-auto px-6 py-2.5 rounded-lg font-bold text-sm text-white transition-all disabled:opacity-40"
              style={{ backgroundColor: '#22c55e' }}
            >
              {loading ? 'Verificando…' : 'Verificar'}
            </button>
          </div>
        </form>

        {/* Visitante de otra sucursal: el dueño decide. Va justo debajo del
            formulario de código —no hasta el final de la página— porque es la
            respuesta a lo que se acaba de escanear, no un aparte. */}
        {visita && (
          <div
            className="rounded-2xl p-6 sm:p-8 text-center"
            style={{ backgroundColor: 'rgba(249,115,22,0.08)', border: '2px solid #f97316' }}
          >
            <div className="text-6xl mb-3">⚠️</div>
            <p className="text-2xl sm:text-3xl font-black" style={{ color: '#f97316' }}>
              OTRA SUCURSAL
            </p>
            <p className="text-lg sm:text-xl font-bold text-white mt-2">{visita.socio}</p>
            <p className="text-sm mt-1" style={{ color: '#8b949e' }}>
              Su membresía es de <span className="text-white font-semibold">{visita.sucursal_socio}</span>.
              Está al corriente, pero no pertenece a esta sucursal.
            </p>
            <div className="mt-5 max-w-xs mx-auto space-y-3">
              {visitaError && (
                <p className="text-xs font-semibold" style={{ color: '#ef4444' }}>{visitaError}</p>
              )}
              <p className="text-[10px]" style={{ color: '#8b949e' }}>
                Quedará registrado que lo autorizaste tú.
              </p>
              <div className="flex gap-2">
                <button
                  type="button" onClick={limpiar}
                  className="flex-1 py-2.5 rounded-lg text-xs font-semibold"
                  style={{ border: '1px solid #21262d', color: '#8b949e' }}
                >
                  Negar acceso
                </button>
                <button
                  type="button" onClick={autorizarVisita} disabled={loading}
                  className="flex-1 py-2.5 rounded-lg text-xs font-bold disabled:opacity-40"
                  style={{ backgroundColor: '#f97316', color: '#0d1117' }}
                >
                  {loading ? 'Registrando…' : 'Autorizar entrada'}
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Resultado. Mismo criterio: entre el código y la búsqueda por nombre,
            para que se vea sin bajar la página. Si el motivo es "otra sucursal" se
            pinta ámbar en vez de rojo: no es un rechazo por fraude o vencimiento,
            es un socio legítimo tocando la puerta equivocada. */}
        {result && !visita && (() => {
          const otraSucursal = !result.ok && result.motivo === 'pertenece a otra sucursal'
          const acento = result.ok ? '#22c55e' : otraSucursal ? '#f97316' : '#ef4444'
          const fondo = result.ok
            ? 'rgba(34,197,94,0.08)'
            : otraSucursal ? 'rgba(249,115,22,0.08)' : 'rgba(239,68,68,0.08)'
          return (
            <div
              className="rounded-2xl p-6 sm:p-8 text-center transition-all"
              style={{ backgroundColor: fondo, border: `2px solid ${acento}` }}
            >
              {result.foto ? (
                <img
                  src={result.foto}
                  alt=""
                  className="w-20 h-20 sm:w-24 sm:h-24 rounded-full object-cover mx-auto mb-4"
                  style={{ border: `3px solid ${acento}` }}
                />
              ) : (
                <div className="text-6xl mb-3">{result.ok ? '✅' : '🚫'}</div>
              )}
              <p className="text-2xl sm:text-3xl font-black" style={{ color: acento }}>
                {result.ok ? 'BIENVENIDO' : 'ACCESO DENEGADO'}
              </p>
              {result.socio && (
                <p className="text-lg sm:text-xl font-bold text-white mt-2">{result.socio}</p>
              )}
              {result.ok ? (
                <div className="mt-3 text-sm space-y-1" style={{ color: '#8b949e' }}>
                  <p>Plan: <span className="text-white font-semibold">{result.plan}</span></p>
                  <p>Vence: <span className="text-white font-semibold">{result.vence ?? 'Sin fecha límite'}</span></p>
                  {result.visitante && (
                    <p style={{ color: '#f97316' }}>
                      Visita de <span className="font-semibold">{result.sucursal_socio}</span>
                      {result.autorizado_por && ` · autorizó ${result.autorizado_por}`}
                    </p>
                  )}
                </div>
              ) : (
                <>
                  <p className="mt-3 text-sm font-semibold" style={{ color: acento }}>{result.motivo}</p>
                  {result.sucursal_socio && (
                    <p className="text-xs mt-1" style={{ color: '#8b949e' }}>
                      Pertenece a {result.sucursal_socio}
                    </p>
                  )}
                </>
              )}
            </div>
          )
        })()}

        {/* Búsqueda por nombre: el socio que olvidó su código bloqueaba la fila,
            porque desde el kiosco no había forma de identificarlo. */}
        <div className="rounded-2xl p-4 sm:p-5" style={{ backgroundColor: '#161b22', border: '1px solid #21262d' }}>
          <p className="text-[10px] font-bold tracking-widest mb-2" style={{ color: '#8b949e' }}>
            ¿NO TRAE SU CÓDIGO? BÚSCALO POR NOMBRE O NÚMERO
          </p>
          <form onSubmit={buscarPorNombre} className="flex gap-2">
            <input
              value={busqueda}
              onChange={e => setBusqueda(e.target.value)}
              placeholder="Nombre, apellido o n° de socio"
              autoComplete="off"
              className="flex-1 text-sm rounded-lg px-3 py-2.5 outline-none text-white placeholder:text-[#3d444d]"
              style={{ backgroundColor: '#0d1117', border: '1px solid #21262d' }}
            />
            <button
              type="submit"
              disabled={buscando || busqueda.trim().length < 2}
              className="px-4 py-2.5 rounded-lg text-xs font-bold disabled:opacity-40"
              style={{ backgroundColor: '#21262d', color: '#fff' }}
            >
              {buscando ? '...' : 'Buscar'}
            </button>
          </form>

          {candidatos && candidatos.length === 0 && (
            <p className="text-xs mt-3 text-center" style={{ color: '#3d444d' }}>
              Ningún socio coincide con "{busqueda}"
            </p>
          )}

          {candidatos && candidatos.length > 0 && (
            <div className="mt-3 space-y-2">
              {candidatos.map(c => (
                <div key={c.id} className="flex items-center justify-between gap-3 rounded-lg px-3 py-2.5"
                  style={{ backgroundColor: '#0d1117', border: '1px solid #21262d' }}>
                  <div className="min-w-0">
                    <p className="text-xs font-semibold text-white truncate">
                      {c.nombre}
                      {c.numero_socio != null && (
                        <span className="ml-2 font-mono font-normal" style={{ color: '#22c55e' }}>
                          #{c.numero_socio}
                        </span>
                      )}
                    </p>
                    <p className="text-[10px] truncate" style={{ color: '#8b949e' }}>
                      {c.sucursal || 'Sin sucursal asignada'}
                      {c.al_corriente
                        ? ` · ${c.plan}${c.vence ? ` hasta ${c.vence}` : ''}`
                        : ' · sin membresía vigente'}
                    </p>
                  </div>
                  {/* Antes, un socio sin QR asignado no se podía registrar desde aquí
                      y quedaba en "Sin código QR" sin salida. Su número de socio lo
                      identifica igual, así que el botón ya no depende del QR. */}
                  {(c.token || c.numero_socio != null) ? (
                    <button
                      onClick={() => procesar(c.token || String(c.numero_socio))}
                      disabled={loading}
                      className="px-3 py-2 rounded-lg text-[10px] font-bold shrink-0 disabled:opacity-40"
                      style={{
                        backgroundColor: c.al_corriente ? '#22c55e' : '#21262d',
                        color: c.al_corriente ? '#0d1117' : '#8b949e',
                      }}
                    >
                      Registrar entrada
                    </button>
                  ) : (
                    <span className="text-[10px] shrink-0" style={{ color: '#f97316' }}>
                      Sin código ni número
                    </span>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
