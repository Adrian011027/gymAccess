import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import api from '../api/axios'
import { QRCodeSVG } from 'qrcode.react'
import Markdown from '../components/Markdown'

// Página pública (sin login): el socio llega aquí desde el link que recepción le
// manda por WhatsApp junto con su QR. El QR no se muestra hasta que acepta el
// aviso de privacidad — es la razón de ser de esta pantalla, no un trámite aparte.
export default function AvisoPrivacidad() {
  const { token } = useParams()
  const [estado, setEstado] = useState('cargando') // cargando | error | listo
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const [aceptando, setAceptando] = useState(false)
  const [codigo, setCodigo] = useState(null)

  useEffect(() => {
    api.get(`/legal/publico/${token}/`)
      .then(r => {
        setData(r.data)
        if (r.data.ya_acepto) setCodigo(r.data.codigo_acceso)
        setEstado('listo')
      })
      .catch(err => {
        setError(err.response?.data?.error || 'No se pudo cargar el aviso de privacidad.')
        setEstado('error')
      })
  }, [token])

  const aceptar = async () => {
    setAceptando(true)
    try {
      const { data } = await api.post(`/legal/publico/${token}/aceptar/`)
      setCodigo(data.codigo_acceso)
    } catch {
      setError('No se pudo registrar tu aceptación. Intenta de nuevo.')
    } finally {
      setAceptando(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center py-8 px-4" style={{ backgroundColor: '#0d1117' }}>
      <div className="w-full max-w-lg rounded-2xl p-5 sm:p-8 space-y-5" style={{ backgroundColor: '#161b22', border: '1px solid #21262d' }}>

        {estado === 'cargando' && (
          <p className="text-center text-sm" style={{ color: '#8b949e' }}>Cargando…</p>
        )}

        {estado === 'error' && (
          <p className="text-center text-sm font-semibold" style={{ color: '#ef4444' }}>{error}</p>
        )}

        {estado === 'listo' && !codigo && (
          <>
            <div className="text-center">
              <h1 className="text-lg font-black text-white">{data.gym_nombre}</h1>
              <p className="text-xs mt-1" style={{ color: '#8b949e' }}>Hola {data.socio_nombre}</p>
            </div>

            <div>
              <h2 className="text-sm font-bold text-white mb-2">
                {data.documento.titulo} <span style={{ color: '#8b949e' }}>· v{data.documento.version}</span>
              </h2>
              <div
                className="rounded-xl p-4 max-h-72 overflow-y-auto"
                style={{ backgroundColor: '#0d1117', border: '1px solid #21262d' }}
              >
                <Markdown texto={data.documento.contenido} />
              </div>
            </div>

            {data.requiere_tutor && (
              <p className="text-xs text-center" style={{ color: '#f97316' }}>
                Como socio menor de edad, la aceptación queda registrada a nombre de tu padre, madre o tutor.
              </p>
            )}

            {error && (
              <p className="text-xs text-center font-semibold" style={{ color: '#ef4444' }}>{error}</p>
            )}

            <button
              onClick={aceptar}
              disabled={aceptando}
              className="w-full py-3 rounded-xl font-bold text-sm disabled:opacity-40"
              style={{ backgroundColor: '#22c55e', color: '#0d1117' }}
            >
              {aceptando ? 'Registrando…' : 'Acepto el aviso de privacidad'}
            </button>
          </>
        )}

        {estado === 'listo' && codigo && (
          <div className="text-center space-y-4">
            <p className="text-sm font-semibold" style={{ color: '#22c55e' }}>¡Gracias! Este es tu código de acceso</p>
            <div className="flex justify-center p-4 rounded-xl" style={{ backgroundColor: '#fff' }}>
              <QRCodeSVG value={codigo} size={180} level="M" />
            </div>
            <p className="text-xs font-mono break-all" style={{ color: '#8b949e' }}>{codigo}</p>
            <p className="text-[11px]" style={{ color: '#8b949e' }}>
              Muéstralo en recepción o guárdalo: es tu llave para entrar.
            </p>
          </div>
        )}
      </div>
    </div>
  )
}
