import { useEffect, useState } from 'react'
import api from '../api/axios'
import Markdown from './Markdown'

const CARD_STYLE = { backgroundColor: '#161b22', border: '1px solid #21262d' }

/**
 * Bloquea la aplicación hasta que el usuario acepta los documentos del proveedor
 * que todavía no ha aceptado.
 *
 * Bloquea en vez de avisar a propósito: una aceptación firmada después de haber
 * estado usando el sistema no acredita gran cosa, y es justo lo que se le pediría
 * al proveedor si el pacto se discute.
 *
 * Si el endpoint falla no se bloquea nada: dejar al gym sin poder cobrar porque una
 * consulta secundaria dio error sería peor que el problema que resuelve.
 */
export default function AceptacionLegal() {
  const [pendientes, setPendientes] = useState([])
  const [indice, setIndice] = useState(0)
  const [leido, setLeido] = useState(false)
  const [enviando, setEnviando] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    api.get('/legal/pendientes/')
      .then(r => setPendientes(Array.isArray(r.data) ? r.data : []))
      .catch(() => setPendientes([]))
  }, [])

  const doc = pendientes[indice]
  if (!doc) return null

  const aceptar = async () => {
    setEnviando(true)
    setError('')
    try {
      await api.post('/legal/aceptar/', { documento: doc.id })
      setLeido(false)
      if (indice + 1 < pendientes.length) setIndice(i => i + 1)
      else setPendientes([])
    } catch {
      setError('No se pudo registrar la aceptación. Revisa tu conexión.')
    } finally {
      setEnviando(false)
    }
  }

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 overflow-y-auto"
      style={{ backgroundColor: 'rgba(0,0,0,0.92)' }}>
      <div className="rounded-2xl w-full max-w-2xl my-auto max-h-[92vh] flex flex-col" style={CARD_STYLE}>
        <div className="p-6 pb-4" style={{ borderBottom: '1px solid #21262d' }}>
          <p className="text-[10px] font-bold tracking-widest" style={{ color: '#22c55e' }}>
            ACEPTACIÓN REQUERIDA
            {pendientes.length > 1 && ` · ${indice + 1} DE ${pendientes.length}`}
          </p>
          <h2 className="text-sm font-bold text-white mt-1">{doc.titulo}</h2>
          <p className="text-[10px] mt-0.5" style={{ color: '#8b949e' }}>
            Versión {doc.version} · vigente desde {doc.vigente_desde}
          </p>
        </div>

        {/* El texto scrollea aquí dentro; los botones quedan siempre visibles abajo. */}
        <div className="flex-1 overflow-y-auto px-6 py-4 min-h-0">
          <Markdown texto={doc.contenido} />
        </div>

        <div className="p-6 pt-4 space-y-3" style={{ borderTop: '1px solid #21262d' }}>
          <label className="flex items-start gap-2.5 cursor-pointer">
            <input type="checkbox" checked={leido}
              onChange={e => { setLeido(e.target.checked); setError('') }}
              className="mt-0.5 shrink-0" />
            <span className="text-[11px] leading-relaxed" style={{ color: '#8b949e' }}>
              He leído y acepto este documento en nombre del negocio. Se registrará mi
              nombre, la fecha y la hora.
            </span>
          </label>
          {error && (
            <p className="text-[11px] font-semibold" style={{ color: '#ef4444' }}>{error}</p>
          )}
          <button onClick={aceptar} disabled={!leido || enviando}
            className="w-full py-3 rounded-lg text-sm font-bold disabled:opacity-40"
            style={{ backgroundColor: '#22c55e', color: '#0d1117' }}>
            {enviando ? 'Registrando...' : 'Aceptar y continuar'}
          </button>
        </div>
      </div>
    </div>
  )
}
