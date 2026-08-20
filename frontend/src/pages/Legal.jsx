import { useEffect, useState } from 'react'
import toast from 'react-hot-toast'
import api from '../api/axios'
import Markdown from '../components/Markdown'

const CARD_STYLE = { backgroundColor: '#161b22', border: '1px solid #21262d' }
const INPUT_STYLE = {
  backgroundColor: '#0d1117', border: '1px solid #21262d', color: '#fff',
  borderRadius: '8px', padding: '10px 12px', fontSize: '14px', width: '100%', outline: 'none',
}

const AVISO = 'aviso_privacidad'

// El aviso lo redacta el gym; los otros dos los publica el proveedor del software y
// aquí solo se leen. Si cada gym pudiera reescribir sus propios términos, dejarían
// de respaldar a nadie.
const TIPOS = [
  {
    key: AVISO,
    titulo: 'Aviso de Privacidad',
    para: 'Lo publicas tú para tus socios',
    porque: 'Obligatorio por la LFPDPPP. Mientras no lo publiques, el alta de socios no pide consentimiento y no se guarda evidencia de nada.',
    editable: true,
  },
  {
    key: 'terminos_servicio',
    titulo: 'Términos y Condiciones del software',
    para: 'Los publica el proveedor; tú los aceptas',
    porque: 'Definen qué pasa con tus datos, el nivel de servicio y los límites de responsabilidad.',
    editable: false,
  },
  {
    key: 'convenio_encargado',
    titulo: 'Convenio de Encargado',
    para: 'Lo pactan el gym y el proveedor',
    porque: 'Delimita que tú decides sobre los datos de tus socios y el proveedor solo los opera por tu cuenta.',
    editable: false,
  },
]

const FORM_VACIO = { version: '', titulo: '', contenido: '', vigente_desde: '' }

export default function Legal() {
  const [vigentes, setVigentes] = useState(null)
  const [historial, setHistorial] = useState([])
  const [leyendo, setLeyendo] = useState(null)
  const [modal, setModal] = useState(false)
  const [form, setForm] = useState(FORM_VACIO)
  const [guardando, setGuardando] = useState(false)
  const [error, setError] = useState('')

  const cargar = () => {
    api.get('/legal/documentos/vigentes/').then(r => setVigentes(r.data)).catch(() => setVigentes({}))
    api.get('/legal/documentos/').then(r => setHistorial(r.data)).catch(() => {})
  }
  useEffect(cargar, [])

  const errorDe = err => {
    const d = err.response?.data
    if (typeof d === 'string') return d
    if (typeof d === 'object' && d) return String(Object.values(d).flat()[0])
    return 'No se pudo publicar'
  }

  const abrirNuevaVersion = () => {
    const actual = vigentes?.[AVISO]
    setForm({
      // Se parte del texto vigente: una versión nueva casi siempre es un retoque de
      // la anterior, y volver a escribirlo entero invita a perder cláusulas.
      version: '',
      titulo: actual?.titulo || 'Aviso de Privacidad',
      contenido: actual?.contenido || '',
      vigente_desde: new Date().toISOString().slice(0, 10),
    })
    setError('')
    setModal(true)
  }

  const publicar = async e => {
    e.preventDefault()
    setGuardando(true)
    setError('')
    try {
      await api.post('/legal/documentos/', { ...form, tipo: AVISO })
      toast.success(`Aviso de privacidad v${form.version} publicado`)
      setModal(false)
      setForm(FORM_VACIO)
      cargar()
    } catch (err) {
      setError(errorDe(err))
    } finally {
      setGuardando(false)
    }
  }

  const versionesDe = tipo => historial.filter(d => d.tipo === tipo)

  return (
    <div className="space-y-5">
      <div>
        <h2 className="text-xl font-black text-white uppercase tracking-wide">LEGAL Y PRIVACIDAD</h2>
        <p className="text-xs mt-0.5" style={{ color: '#8b949e' }}>
          Documentos vigentes y evidencia de aceptación
        </p>
      </div>

      {vigentes && !vigentes[AVISO] && (
        <div className="rounded-xl p-4" style={{ backgroundColor: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.3)' }}>
          <p className="text-xs font-bold" style={{ color: '#ef4444' }}>
            Todavía no has publicado tu aviso de privacidad
          </p>
          <p className="text-[10px] mt-1 leading-relaxed" style={{ color: '#8b949e' }}>
            Es obligatorio si tratas datos de socios. Mientras no exista, el alta no pide
            consentimiento y no se guarda evidencia de que nadie aceptó nada, que es
            justamente lo que te respaldaría ante una reclamación.
          </p>
        </div>
      )}

      <div className="space-y-4">
        {TIPOS.map(t => {
          const doc = vigentes?.[t.key]
          const versiones = versionesDe(t.key)
          return (
            <div key={t.key} className="rounded-xl p-6" style={CARD_STYLE}>
              <div className="flex items-start justify-between gap-3 flex-wrap">
                <div className="min-w-0">
                  <h3 className="text-sm font-bold text-white">{t.titulo}</h3>
                  <p className="text-[10px] mt-0.5" style={{ color: '#8b949e' }}>{t.para}</p>
                  <p className="text-[10px] mt-2 leading-relaxed max-w-lg" style={{ color: '#8b949e' }}>
                    {t.porque}
                  </p>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  {doc && (
                    <button onClick={() => setLeyendo(doc)}
                      className="px-3 py-2 rounded-lg text-xs font-semibold"
                      style={{ border: '1px solid #21262d', color: '#8b949e' }}>
                      Leer
                    </button>
                  )}
                  {t.editable && (
                    <button onClick={abrirNuevaVersion}
                      className="px-3 py-2 rounded-lg text-xs font-bold"
                      style={{ backgroundColor: '#22c55e', color: '#0d1117' }}>
                      {doc ? 'Nueva versión' : 'Publicar'}
                    </button>
                  )}
                </div>
              </div>

              <div className="mt-4 pt-4" style={{ borderTop: '1px solid #21262d' }}>
                {doc ? (
                  <div className="flex items-center gap-4 flex-wrap text-[10px]" style={{ color: '#8b949e' }}>
                    <span className="px-2 py-1 rounded font-semibold"
                      style={{ backgroundColor: 'rgba(34,197,94,0.1)', color: '#22c55e' }}>
                      Vigente · v{doc.version}
                    </span>
                    <span>Desde {doc.vigente_desde}</span>
                    {doc.publicado_por_nombre && <span>Publicado por {doc.publicado_por_nombre}</span>}
                    {versiones.length > 1 && <span>{versiones.length} versiones en total</span>}
                  </div>
                ) : (
                  <p className="text-[10px]" style={{ color: '#3d444d' }}>
                    {t.editable
                      ? 'Sin publicar'
                      : 'El proveedor todavía no ha publicado este documento.'}
                  </p>
                )}
              </div>

              {/* Las versiones viejas no se borran: un consentimiento firmado apunta a
                  la que el socio leyó, y sin ella la evidencia no dice nada. */}
              {versiones.length > 1 && (
                <div className="mt-3 space-y-1">
                  {versiones.filter(v => v.id !== doc?.id).map(v => (
                    <button key={v.id} onClick={() => setLeyendo(v)}
                      className="flex items-center gap-3 w-full text-left px-3 py-2 rounded-lg transition-opacity hover:opacity-75"
                      style={{ backgroundColor: '#0d1117', border: '1px solid #21262d' }}>
                      <span className="text-[10px] font-mono" style={{ color: '#8b949e' }}>v{v.version}</span>
                      <span className="text-[10px]" style={{ color: '#3d444d' }}>desde {v.vigente_desde}</span>
                    </button>
                  ))}
                </div>
              )}
            </div>
          )
        })}
      </div>

      {/* Lector */}
      {leyendo && (
        <div className="fixed inset-0 flex items-center justify-center z-50 p-4 overflow-y-auto" style={{ backgroundColor: 'rgba(0,0,0,0.7)' }}>
          <div className="rounded-2xl p-6 w-full max-w-2xl my-auto max-h-[90vh] overflow-y-auto" style={CARD_STYLE}>
            <div className="flex items-start justify-between gap-3 mb-4 sticky top-0 pb-3"
              style={{ backgroundColor: '#161b22', borderBottom: '1px solid #21262d' }}>
              <div>
                <h2 className="text-sm font-bold text-white">{leyendo.titulo}</h2>
                <p className="text-[10px] mt-0.5" style={{ color: '#8b949e' }}>
                  Versión {leyendo.version} · vigente desde {leyendo.vigente_desde}
                </p>
              </div>
              <button onClick={() => setLeyendo(null)} style={{ color: '#8b949e' }} className="hover:text-white shrink-0">
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" /></svg>
              </button>
            </div>
            <Markdown texto={leyendo.contenido} />
          </div>
        </div>
      )}

      {/* Publicar versión del aviso */}
      {modal && (
        <div className="fixed inset-0 flex items-center justify-center z-50 p-4 overflow-y-auto" style={{ backgroundColor: 'rgba(0,0,0,0.7)' }}>
          <div className="rounded-2xl p-6 w-full max-w-2xl my-auto max-h-[90vh] overflow-y-auto" style={CARD_STYLE}>
            <h2 className="text-sm font-bold text-white mb-1">Publicar aviso de privacidad</h2>
            <p className="text-[10px] mb-5 leading-relaxed" style={{ color: '#8b949e' }}>
              Se crea una versión nueva; la anterior se conserva porque los
              consentimientos ya firmados apuntan a ella. Hay un borrador listo para
              copiar en{' '}
              <code className="font-mono" style={{ color: '#22c55e' }}>legal/aviso-privacidad.md</code>
              {' '}del proyecto. Revísalo con un abogado antes de publicarlo.
            </p>
            <form onSubmit={publicar} className="space-y-3">
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <div>
                  <label className="text-[10px] font-bold tracking-widest" style={{ color: '#8b949e' }}>VERSIÓN</label>
                  <input required value={form.version} placeholder="1.0"
                    onChange={e => setForm(f => ({ ...f, version: e.target.value }))}
                    className="mt-1" style={INPUT_STYLE} />
                </div>
                <div className="sm:col-span-2">
                  <label className="text-[10px] font-bold tracking-widest" style={{ color: '#8b949e' }}>TÍTULO</label>
                  <input required value={form.titulo}
                    onChange={e => setForm(f => ({ ...f, titulo: e.target.value }))}
                    className="mt-1" style={INPUT_STYLE} />
                </div>
              </div>
              <div>
                <label className="text-[10px] font-bold tracking-widest" style={{ color: '#8b949e' }}>
                  VIGENTE DESDE
                </label>
                <input required type="date" value={form.vigente_desde}
                  onChange={e => setForm(f => ({ ...f, vigente_desde: e.target.value }))}
                  className="mt-1 dark-date" style={{ ...INPUT_STYLE, colorScheme: 'dark' }} />
                <p className="text-[10px] mt-1" style={{ color: '#3d444d' }}>
                  Una fecha futura deja la versión preparada sin que empiece a exigirse todavía.
                </p>
              </div>
              <div>
                <label className="text-[10px] font-bold tracking-widest" style={{ color: '#8b949e' }}>
                  TEXTO DEL AVISO (MARKDOWN)
                </label>
                <textarea required rows={16} value={form.contenido}
                  onChange={e => setForm(f => ({ ...f, contenido: e.target.value }))}
                  className="mt-1 font-mono"
                  style={{ ...INPUT_STYLE, fontSize: '12px', lineHeight: '1.6', resize: 'vertical' }} />
              </div>
              {error && (
                <p className="text-[11px] font-semibold" style={{ color: '#ef4444' }}>{error}</p>
              )}
              <div className="flex gap-3 pt-2">
                <button type="button" onClick={() => setModal(false)}
                  className="flex-1 py-2.5 rounded-lg text-xs font-semibold"
                  style={{ border: '1px solid #21262d', color: '#8b949e', backgroundColor: 'transparent' }}>
                  Cancelar
                </button>
                <button type="submit" disabled={guardando}
                  className="flex-1 py-2.5 rounded-lg text-xs font-bold disabled:opacity-50"
                  style={{ backgroundColor: '#22c55e', color: '#0d1117' }}>
                  {guardando ? 'Publicando...' : 'Publicar'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
