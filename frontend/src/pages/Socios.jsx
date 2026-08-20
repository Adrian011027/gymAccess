import { useEffect, useState } from 'react'
import { QRCodeSVG } from 'qrcode.react'
import api from '../api/axios'
import toast from 'react-hot-toast'
import { useAuth } from '../context/AuthContext'
import Markdown from '../components/Markdown'

const CARD_STYLE = { backgroundColor: '#161b22', border: '1px solid #21262d' }
const INPUT_STYLE = { backgroundColor: '#0d1117', border: '1px solid #21262d', color: '#fff' }
// `colorScheme: dark` es lo único que hace que el navegador pinte el calendario y su
// icono en oscuro; sin esto el selector de fecha sale blanco sobre el panel negro.
const DATE_STYLE = { ...INPUT_STYLE, colorScheme: 'dark' }

const EMPTY = {
  nombre: '', apellido: '', email: '', telefono: '', sexo: '',
  fecha_nacimiento: '', plan_id: '', sucursal: '',
  tutor_nombre: '', tutor_parentesco: '', tutor_telefono: '',
  acepta_aviso: false,
}

// Un menor no puede consentir el tratamiento de sus datos: lo hace quien ejerce la
// patria potestad. Se calcula aquí y en el backend con la misma regla.
function esMenorDeEdad(fechaNac) {
  if (!fechaNac) return false
  const d = new Date(fechaNac)
  const hoy = new Date()
  let años = hoy.getFullYear() - d.getFullYear()
  if (hoy < new Date(hoy.getFullYear(), d.getMonth(), d.getDate())) años--
  return años < 18
}

const AVATAR_COLORS = ['#f97316', '#a855f7', '#3b82f6', '#22c55e', '#ef4444', '#eab308', '#06b6d4']
function avatarColor(name) { return AVATAR_COLORS[(name?.charCodeAt(0) || 0) % AVATAR_COLORS.length] }
function initials(n = '', a = '') { return `${n[0] || ''}${a[0] || ''}`.toUpperCase() }

function edad(fechaNac) {
  if (!fechaNac) return '—'
  const d = new Date(fechaNac)
  const hoy = new Date()
  let y = hoy.getFullYear() - d.getFullYear()
  if (hoy < new Date(hoy.getFullYear(), d.getMonth(), d.getDate())) y--
  return y
}

function antiguedad(creadoEn) {
  if (!creadoEn) return '—'
  const d = new Date(creadoEn)
  const hoy = new Date()
  const meses = (hoy.getFullYear() - d.getFullYear()) * 12 + (hoy.getMonth() - d.getMonth())
  const y = Math.floor(meses / 12)
  const m = meses % 12
  return `${y}a ${m}m`
}

const PLAN_COLORS = {
  'Socio Regular': { bg: 'rgba(34,197,94,0.15)', color: '#22c55e' },
}
function planBadge(nombre) {
  const c = PLAN_COLORS[nombre] || { bg: 'rgba(139,148,158,0.15)', color: '#8b949e' }
  return c
}

export default function Socios() {
  const { sucursalId, isAdmin } = useAuth()
  const [socios, setSocios] = useState([])
  const [planes, setPlanes] = useState([])
  const [sucursales, setSucursales] = useState([])
  const [modal, setModal] = useState(false)
  const [form, setForm] = useState(EMPTY)
  const [search, setSearch] = useState('')
  const [filtro, setFiltro] = useState('todos')
  const [loading, setLoading] = useState(false)
  const [qrModal, setQrModal] = useState(null)
  const [qrLoading, setQrLoading] = useState(false)
  // Null mientras carga; luego el documento vigente o undefined si el gym no publicó
  // ninguno. Sin aviso publicado no hay nada que aceptar y el alta no lo pide.
  const [aviso, setAviso] = useState(null)
  const [leyendoAviso, setLeyendoAviso] = useState(false)
  // Derechos ARCO: el socio puede pedir ver sus datos y pedir que se borren.
  const [cancelando, setCancelando] = useState(null)
  const [cancelPass, setCancelPass] = useState('')
  const [cancelTexto, setCancelTexto] = useState('')
  const [cancelError, setCancelError] = useState('')
  const [cancelLoading, setCancelLoading] = useState(false)
  // Cambiar la fecha de próximo pago exige contraseña del dueño; este estado guarda
  // el cambio pendiente mientras se pide esa autorización.
  const [autorizacion, setAutorizacion] = useState(null)
  const [authPass, setAuthPass] = useState('')
  const [authMotivo, setAuthMotivo] = useState('')
  const [authLoading, setAuthLoading] = useState(false)
  const [authError, setAuthError] = useState('')

  const load = () => api.get('/socios/').then(r => setSocios(r.data)).catch(() => {})
  useEffect(() => {
    load()
    api.get('/socios/planes/').then(r => setPlanes(r.data)).catch(() => {})
    api.get('/gyms/sucursales/').then(r => setSucursales(r.data)).catch(() => {})
    api.get('/legal/documentos/vigentes/')
      .then(r => setAviso(r.data?.aviso_privacidad || undefined))
      .catch(() => setAviso(undefined))
  }, [])

  // El lector de huella todavía no está soportado (no hay agente local instalado en
  // las sucursales), así que la identificación del socio va por QR.
  const abrirQR = socio => setQrModal(socio)

  const asignarQR = async () => {
    if (!qrModal) return
    setQrLoading(true)
    try {
      const { data } = await api.post('/accesos/asignar-qr/', { socio_id: qrModal.id })
      setQrModal(m => ({ ...m, codigo_acceso: data.token }))
      toast.success('Código QR asignado')
      load()
    } catch (err) {
      toast.error(err.response?.data?.socio_id || err.response?.data?.error || 'No se pudo asignar el código')
    } finally {
      setQrLoading(false)
    }
  }

  const imprimirQR = () => {
    // Se imprime el nodo del QR tal cual: abrir una ventana con el SVG serializado
    // evita depender de una librería de PDF solo para una credencial.
    const svg = document.getElementById('qr-socio')
    if (!svg) return
    const win = window.open('', '_blank', 'width=420,height=520')
    if (!win) return
    win.document.write(`<html><body style="font-family:sans-serif;text-align:center;padding:32px">
      <h3>${qrModal.nombre} ${qrModal.apellido}</h3>
      ${new XMLSerializer().serializeToString(svg)}
      <p style="font-family:monospace;font-size:12px">${qrModal.codigo_acceso}</p>
    </body></html>`)
    win.document.close()
    win.focus()
    win.print()
  }

  const exportarDatos = async socio => {
    try {
      const { data } = await api.get(`/socios/${socio.id}/datos-personales/`)
      // Se entrega como archivo porque es lo que el socio pide al ejercer el derecho
      // de acceso: un documento con todo lo que el gym guarda de él.
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `datos-${socio.nombre}-${socio.apellido}-${new Date().toISOString().slice(0, 10)}.json`
      a.click()
      URL.revokeObjectURL(url)
      toast.success('Datos exportados')
    } catch (err) {
      toast.error(errorDe(err))
    }
  }

  const confirmarCancelacion = async e => {
    e.preventDefault()
    if (cancelTexto.trim().toLowerCase() !== 'cancelar') {
      setCancelError('Escribe exactamente "cancelar" para confirmar.')
      return
    }
    setCancelLoading(true)
    setCancelError('')
    try {
      await api.post(`/socios/${cancelando.id}/cancelar-datos/`, { password: cancelPass })
      toast.success('Datos personales cancelados')
      setCancelando(null)
      setCancelPass('')
      load()
    } catch (err) {
      setCancelError(
        err.response?.status === 403
          ? 'Contraseña de autorización incorrecta.'
          : errorDe(err)
      )
      setCancelPass('')
    } finally {
      setCancelLoading(false)
    }
  }

  const errorDe = err => {
    const d = err.response?.data
    if (typeof d === 'object' && d) return String(Object.values(d).flat()[0])
    return 'Error al guardar'
  }

  const fechaOriginal = form.membresia_reciente?.fecha_fin || ''

  const guardarSocio = async () => {
    // plan_id y proximo_pago no son campos de Socio: se extraen solo para excluirlos.
    const { plan_id: _p, proximo_pago: _f, ...socioData } = form
    await api.patch(`/socios/${form.id}/`, socioData)
  }

  const save = async e => {
    e.preventDefault()

    // Si movió la fecha de próximo pago, nada se guarda hasta que el dueño autorice:
    // así una autorización rechazada no deja el resto del formulario ya aplicado.
    if (form.id && form.proximo_pago && form.proximo_pago !== fechaOriginal) {
      setAuthPass('')
      setAuthMotivo('')
      setAuthError('')
      setAutorizacion({
        membresiaId: form.membresia_reciente.id,
        socio: `${form.nombre} ${form.apellido}`,
        de: fechaOriginal,
        a: form.proximo_pago,
      })
      return
    }

    setLoading(true)
    try {
      const { plan_id, proximo_pago: _f, acepta_aviso, ...socioData } = form
      socioData.sucursal = socioData.sucursal || null
      if (form.id) {
        await api.patch(`/socios/${form.id}/`, socioData)
        toast.success('Socio actualizado')
      } else {
        socioData.acepta_aviso = acepta_aviso
        const { data: socio } = await api.post('/socios/', socioData)
        const plan = planes.find(p => p.id === Number(plan_id))
        const hoy = new Date().toISOString().slice(0, 10)
        const fin = plan?.duracion_dias
          ? new Date(Date.now() + plan.duracion_dias * 86400000).toISOString().slice(0, 10)
          : null
        try {
          await api.post('/socios/membresias/', {
            socio: socio.id,
            plan: plan_id,
            // La membresía se cobra en la sucursal del socio; `sucursales[0]` mandaba
            // el ingreso al primer local de la lista, que rara vez era el correcto.
            sucursal: socioData.sucursal || sucursales[0]?.id,
            fecha_inicio: hoy,
            fecha_fin: fin,
            estado: 'activa',
          })
          toast.success('Socio registrado')
        } catch (err) {
          // El socio ya existe: decirlo explícitamente evita que lo den de alta otra
          // vez creyendo que no se guardó nada.
          toast.error(
            `Socio creado, pero no se pudo asignar el plan (${errorDe(err)}). ` +
            'Asígnalo desde Membresías.'
          )
        }
      }
      setModal(false)
      setForm(EMPTY)
      load()
    } catch (err) {
      toast.error(errorDe(err))
    } finally {
      setLoading(false)
    }
  }

  const confirmarAutorizacion = async e => {
    e.preventDefault()
    setAuthLoading(true)
    setAuthError('')
    try {
      await api.post(`/socios/membresias/${autorizacion.membresiaId}/ajustar-vencimiento/`, {
        fecha_fin: autorizacion.a,
        password: authPass,
        motivo: authMotivo,
      })
      await guardarSocio()
      toast.success('Fecha de próximo pago actualizada')
      setAutorizacion(null)
      setAuthPass('')
      setModal(false)
      setForm(EMPTY)
      load()
    } catch (err) {
      const s = err.response?.status
      if (s === 403) setAuthError('Contraseña de autorización incorrecta.')
      else if (s === 429) setAuthError('Demasiados intentos. Espera un minuto.')
      else setAuthError(err.response?.data?.fecha_fin?.[0] || 'No se pudo aplicar el cambio.')
      setAuthPass('')
    } finally {
      setAuthLoading(false)
    }
  }

  const activos = socios.filter(s => s.activo).length
  const inactivos = socios.filter(s => !s.activo).length

  const filtered = socios
    .filter(s => filtro === 'activos' ? s.activo : filtro === 'inactivos' ? !s.activo : true)
    .filter(s =>
      `${s.nombre} ${s.apellido} ${s.email} ${s.numero_socio ?? ''}`
        .toLowerCase().includes(search.toLowerCase())
    )

  const inputCls = 'w-full rounded-lg px-3 py-2 text-sm mt-1 focus:outline-none text-white'

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-xl font-black text-white uppercase tracking-wide">SOCIOS</h2>
          <p className="text-xs mt-0.5" style={{ color: '#8b949e' }}>{activos} activos · {inactivos} inactivos</p>
        </div>
        <button
          onClick={() => { setForm({ ...EMPTY, sucursal: sucursalId || '' }); setModal(true) }}
          className="flex items-center gap-2 px-4 py-2.5 rounded-lg text-xs font-bold text-white transition-all"
          style={{ backgroundColor: '#22c55e', color: '#0d1117' }}
          onMouseEnter={e => e.currentTarget.style.backgroundColor = '#16a34a'}
          onMouseLeave={e => e.currentTarget.style.backgroundColor = '#22c55e'}
        >
          + Nuevo Socio
        </button>
      </div>

      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div className="flex items-center gap-2 px-3 py-2 rounded-lg flex-1 sm:max-w-md" style={CARD_STYLE}>
          <svg className="w-4 h-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" style={{ color: '#8b949e' }}>
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
          <input
            type="text"
            placeholder="Buscar por nombre..."
            value={search}
            onChange={e => setSearch(e.target.value)}
            className="bg-transparent text-sm w-full outline-none text-white placeholder:text-[#3d444d]"
          />
        </div>
        <div className="flex gap-1 flex-wrap">
          {[['todos', 'Todos'], ['activos', 'Activos'], ['inactivos', 'Inactivos']].map(([v, l]) => (
            <button
              key={v}
              onClick={() => setFiltro(v)}
              className="px-4 py-2 rounded-lg text-xs font-semibold transition-all"
              style={filtro === v
                ? { backgroundColor: '#22c55e', color: '#0d1117' }
                : { backgroundColor: '#161b22', color: '#8b949e', border: '1px solid #21262d' }
              }
            >{l}</button>
          ))}
        </div>
      </div>

      <div className="rounded-xl overflow-hidden" style={CARD_STYLE}>
        <div className="overflow-x-auto">
        <table className="w-full text-sm min-w-[920px]">
          <thead style={{ borderBottom: '1px solid #21262d' }}>
            <tr>
              {['SOCIO', 'N.° SOCIO', 'EDAD', 'PLAN', 'ANTIGÜEDAD', 'F. NACIMIENTO', 'PRÓX. PAGO', 'ESTADO', ''].map(h => (
                <th key={h} className="px-4 py-3 text-left text-[10px] font-bold tracking-widest" style={{ color: '#8b949e' }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {filtered.map((s, i) => {
              const plan = s.membresia_activa?.plan
              const pc = planBadge(plan)
              const vence = s.membresia_activa?.fecha_fin
              const venceHoy = vence && new Date(vence).toDateString() === new Date().toDateString()
              return (
                <tr key={s.id} style={{ borderBottom: i < filtered.length - 1 ? '1px solid #21262d' : undefined }}>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 rounded-full flex items-center justify-center text-[10px] font-bold shrink-0"
                        style={{ backgroundColor: avatarColor(s.nombre), color: '#0d1117' }}>
                        {initials(s.nombre, s.apellido)}
                      </div>
                      <div className="min-w-0">
                        <span className="text-xs font-semibold text-white">{s.nombre} {s.apellido}</span>
                        {/* Se ve a los socios de todas las sucursales, pero se marca
                            cuáles no son de aquí: ver no es lo mismo que dejar entrar. */}
                        {s.sucursal && sucursalId && s.sucursal !== sucursalId && (
                          <span className="block text-[10px] font-semibold" style={{ color: '#f97316' }}>
                            ⌂ {s.sucursal_nombre}
                          </span>
                        )}
                        {/* Un socio sin consentimiento registrado es un hueco legal
                            abierto, no un detalle: se ve desde el listado. */}
                        {aviso && !s.consentimiento && (
                          <span className="block text-[10px] font-semibold" title="Falta que acepte el aviso de privacidad"
                            style={{ color: '#ef4444' }}>
                            ⚠ Sin consentimiento
                          </span>
                        )}
                        {!s.sucursal && (
                          <span className="block text-[10px] font-semibold" title="Sin sucursal, la política de acceso no se le aplica"
                            style={{ color: '#ef4444' }}>
                            ⚠ Sin sucursal
                          </span>
                        )}
                      </div>
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    {/* Número de socio: consecutivo por gym, para decirlo en voz alta,
                        imprimirlo y buscarlo a mano. No es el código del QR —ese sigue
                        siendo el token con parte aleatoria del modal "ver código"—,
                        porque un consecutivo ahí se adivina probando números seguidos. */}
                    {s.numero_socio != null ? (
                      <button
                        onClick={() => { navigator.clipboard.writeText(String(s.numero_socio)); toast.success('Número copiado') }}
                        title="Clic para copiar"
                        className="text-xs font-mono font-bold px-2 py-1 rounded transition-opacity hover:opacity-70"
                        style={{ backgroundColor: 'rgba(139,148,158,0.1)', color: '#fff' }}
                      >
                        {s.numero_socio}
                      </button>
                    ) : (
                      <span className="text-[10px]" style={{ color: '#3d444d' }}>—</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-xs" style={{ color: '#8b949e' }}>{edad(s.fecha_nacimiento)}</td>
                  <td className="px-4 py-3">
                    {plan
                      ? <span className="text-[10px] px-2 py-0.5 rounded font-semibold" style={{ backgroundColor: pc.bg, color: pc.color }}>{plan}</span>
                      : <span className="text-[10px]" style={{ color: '#3d444d' }}>Sin plan</span>
                    }
                  </td>
                  <td className="px-4 py-3 text-xs" style={{ color: '#8b949e' }}>{antiguedad(s.creado_en)}</td>
                  <td className="px-4 py-3 text-xs" style={{ color: '#8b949e' }}>{s.fecha_nacimiento || '—'}</td>
                  <td className="px-4 py-3 text-xs font-semibold" style={{ color: vencePronto(vence) ? '#f97316' : '#8b949e' }}>
                    {vence || '—'}
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-1.5">
                      <span className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: s.activo ? '#22c55e' : '#ef4444' }} />
                      <span className="text-[10px] font-semibold" style={{ color: s.activo ? '#22c55e' : '#ef4444' }}>
                        {s.activo ? 'Activo' : 'Inactivo'}
                      </span>
                    </div>
                  </td>
                  <td className="px-4 py-3 text-right">
                    <div className="flex items-center justify-end gap-3">
                      <button onClick={() => abrirQR(s)} title="Asignar y ver código QR" style={{ color: '#8b949e' }} className="hover:text-white transition-colors">
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4h6v6H4V4zm10 0h6v6h-6V4zM4 14h6v6H4v-6zm10 4h2m-2 2h6m0-6v2m0 0h-4" />
                        </svg>
                      </button>
                      <button onClick={() => { setForm({ ...s, proximo_pago: s.membresia_reciente?.fecha_fin || '' }); setModal(true) }} style={{ color: '#8b949e' }} className="hover:text-white transition-colors">
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                        </svg>
                      </button>
                      {/* Derechos ARCO. Solo admin: son solicitudes formales con
                          plazo legal, no una operación de mostrador. */}
                      {isAdmin && !s.anonimizado_en && (
                        <>
                          <button onClick={() => exportarDatos(s)} title="Exportar sus datos (derecho de acceso)"
                            style={{ color: '#8b949e' }} className="hover:text-white transition-colors">
                            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                            </svg>
                          </button>
                          <button onClick={() => { setCancelando(s); setCancelPass(''); setCancelTexto(''); setCancelError('') }}
                            title="Cancelar sus datos personales (derecho de cancelación)"
                            style={{ color: '#8b949e' }} className="transition-colors"
                            onMouseEnter={e => e.currentTarget.style.color = '#ef4444'}
                            onMouseLeave={e => e.currentTarget.style.color = '#8b949e'}>
                            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                            </svg>
                          </button>
                        </>
                      )}
                    </div>
                  </td>
                </tr>
              )
            })}
            {filtered.length === 0 && (
              <tr><td colSpan={9} className="px-4 py-10 text-center text-xs" style={{ color: '#3d444d' }}>Sin socios</td></tr>
            )}
          </tbody>
        </table>
        </div>
      </div>

      {modal && (
        <div className="fixed inset-0 flex items-center justify-center z-50 p-4 overflow-y-auto" style={{ backgroundColor: 'rgba(0,0,0,0.7)' }}>
          <div className="rounded-2xl p-6 w-full max-w-md my-auto max-h-[90vh] overflow-y-auto" style={CARD_STYLE}>
            <div className="flex items-center justify-between mb-5">
              <h2 className="text-sm font-bold text-white">{form.id ? 'Editar socio' : 'Nuevo socio'}</h2>
              <button onClick={() => setModal(false)} style={{ color: '#8b949e' }} className="hover:text-white">
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" /></svg>
              </button>
            </div>
            <form onSubmit={save} className="space-y-3">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-[10px] font-bold tracking-widest" style={{ color: '#8b949e' }}>NOMBRE</label>
                  <input required value={form.nombre} onChange={e => setForm(f => ({ ...f, nombre: e.target.value }))} className={inputCls} style={INPUT_STYLE} />
                </div>
                <div>
                  <label className="text-[10px] font-bold tracking-widest" style={{ color: '#8b949e' }}>APELLIDO</label>
                  <input required value={form.apellido} onChange={e => setForm(f => ({ ...f, apellido: e.target.value }))} className={inputCls} style={INPUT_STYLE} />
                </div>
              </div>
              <div>
                <label className="text-[10px] font-bold tracking-widest" style={{ color: '#8b949e' }}>EMAIL</label>
                <input type="email" value={form.email} onChange={e => setForm(f => ({ ...f, email: e.target.value }))} className={inputCls} style={INPUT_STYLE} />
              </div>
              <div>
                <label className="text-[10px] font-bold tracking-widest" style={{ color: '#8b949e' }}>TELÉFONO</label>
                <input value={form.telefono} onChange={e => setForm(f => ({ ...f, telefono: e.target.value }))} className={inputCls} style={INPUT_STYLE} />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-[10px] font-bold tracking-widest" style={{ color: '#8b949e' }}>SEXO</label>
                  <select value={form.sexo} onChange={e => setForm(f => ({ ...f, sexo: e.target.value }))} className={inputCls} style={INPUT_STYLE}>
                    <option value="">—</option>
                    <option value="M">Masculino</option>
                    <option value="F">Femenino</option>
                    <option value="O">Otro</option>
                  </select>
                </div>
                <div>
                  <label className="text-[10px] font-bold tracking-widest" style={{ color: '#8b949e' }}>FECHA NACIMIENTO</label>
                  <input
                    type="date"
                    max={new Date().toISOString().slice(0, 10)}
                    value={form.fecha_nacimiento || ''}
                    onChange={e => setForm(f => ({
                      ...f,
                      fecha_nacimiento: e.target.value,
                      // Si deja de ser menor, los datos del tutor sobran: dejarlos
                      // guardados diría que alguien responde por un adulto.
                      ...(esMenorDeEdad(e.target.value)
                        ? {}
                        : { tutor_nombre: '', tutor_parentesco: '', tutor_telefono: '' }),
                    }))}
                    className={`${inputCls} dark-date`}
                    style={DATE_STYLE}
                  />
                </div>
              </div>
              {form.id && form.membresia_reciente && (
                <div className="rounded-lg p-3" style={{ backgroundColor: '#0d1117', border: '1px solid #21262d' }}>
                  <label className="text-[10px] font-bold tracking-widest" style={{ color: '#8b949e' }}>
                    PRÓXIMO PAGO
                  </label>
                  <input
                    type="date"
                    value={form.proximo_pago || ''}
                    onChange={e => setForm(f => ({ ...f, proximo_pago: e.target.value }))}
                    className={`${inputCls} dark-date`}
                    style={DATE_STYLE}
                  />
                  <p className="text-[10px] mt-1.5 leading-relaxed" style={{ color: '#8b949e' }}>
                    Plan {form.membresia_reciente.plan} · estado {form.membresia_reciente.estado}
                  </p>
                  {form.proximo_pago !== fechaOriginal && (
                    <p className="text-[10px] mt-1 font-semibold" style={{ color: '#f97316' }}>
                      ⚠ Cambiar esta fecha requiere la contraseña del dueño.
                    </p>
                  )}
                </div>
              )}
              {/* Datos del tutor: aparecen solos cuando la fecha de nacimiento dice
                  que es menor. El backend los exige con la misma regla. */}
              {esMenorDeEdad(form.fecha_nacimiento) && (
                <div className="rounded-lg p-3 space-y-3" style={{ backgroundColor: '#0d1117', border: '1px solid rgba(249,115,22,0.35)' }}>
                  <p className="text-[10px] font-bold tracking-widest" style={{ color: '#f97316' }}>
                    SOCIO MENOR DE EDAD · DATOS DEL TUTOR
                  </p>
                  <p className="text-[10px] leading-relaxed" style={{ color: '#8b949e' }}>
                    Un menor no puede consentir el tratamiento de sus datos: lo hace
                    quien ejerce la patria potestad o la tutela.
                  </p>
                  <div>
                    <label className="text-[10px] font-bold tracking-widest" style={{ color: '#8b949e' }}>
                      NOMBRE DEL PADRE, MADRE O TUTOR <span style={{ color: '#f97316' }}>*</span>
                    </label>
                    <input required value={form.tutor_nombre || ''}
                      onChange={e => setForm(f => ({ ...f, tutor_nombre: e.target.value }))}
                      className={inputCls} style={INPUT_STYLE} />
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="text-[10px] font-bold tracking-widest" style={{ color: '#8b949e' }}>PARENTESCO</label>
                      <select value={form.tutor_parentesco || ''}
                        onChange={e => setForm(f => ({ ...f, tutor_parentesco: e.target.value }))}
                        className={inputCls} style={INPUT_STYLE}>
                        <option value="">—</option>
                        <option value="Madre">Madre</option>
                        <option value="Padre">Padre</option>
                        <option value="Tutor legal">Tutor legal</option>
                      </select>
                    </div>
                    <div>
                      <label className="text-[10px] font-bold tracking-widest" style={{ color: '#8b949e' }}>
                        TELÉFONO <span style={{ color: '#f97316' }}>*</span>
                      </label>
                      <input required value={form.tutor_telefono || ''}
                        onChange={e => setForm(f => ({ ...f, tutor_telefono: e.target.value }))}
                        className={inputCls} style={INPUT_STYLE} />
                    </div>
                  </div>
                </div>
              )}

              <div>
                <label className="text-[10px] font-bold tracking-widest" style={{ color: '#8b949e' }}>
                  SUCURSAL <span style={{ color: '#f97316' }}>*</span>
                </label>
                <select
                  required
                  value={form.sucursal || ''}
                  onChange={e => setForm(f => ({ ...f, sucursal: e.target.value }))}
                  className={inputCls} style={INPUT_STYLE}
                >
                  <option value="">Selecciona una sucursal</option>
                  {sucursales
                    .filter(s => !sucursalId || s.id === sucursalId)
                    .map(s => (
                      <option key={s.id} value={s.id}>{s.nombre}</option>
                    ))}
                </select>
                <p className="text-[10px] mt-1" style={{ color: '#3d444d' }}>
                  Dónde está registrado y dónde paga. Puede entrenar en otras según la política del gym.
                </p>
              </div>
              {!form.id && (
                <div>
                  <label className="text-[10px] font-bold tracking-widest" style={{ color: '#8b949e' }}>
                    PLAN <span style={{ color: '#f97316' }}>*</span>
                  </label>
                  <select
                    required
                    value={form.plan_id}
                    onChange={e => setForm(f => ({ ...f, plan_id: e.target.value }))}
                    className={inputCls} style={INPUT_STYLE}
                  >
                    <option value="">Selecciona un plan</option>
                    {planes.map(p => (
                      <option key={p.id} value={p.id}>{p.nombre} — ${p.precio}</option>
                    ))}
                  </select>
                  {planes.length === 0 && (
                    <p className="text-[10px] mt-1 font-semibold" style={{ color: '#f97316' }}>
                      ⚠ No hay planes creados. Crea uno en Configuración antes de dar de alta socios.
                    </p>
                  )}
                </div>
              )}
              {/* Solo si el gym ya publicó un aviso: no se puede consentir un
                  documento que no existe. El backend aplica la misma condición. */}
              {!form.id && aviso && (
                <label className="flex items-start gap-2.5 rounded-lg p-3 cursor-pointer"
                  style={{ backgroundColor: '#0d1117', border: '1px solid #21262d' }}>
                  <input
                    type="checkbox" required
                    checked={!!form.acepta_aviso}
                    onChange={e => setForm(f => ({ ...f, acepta_aviso: e.target.checked }))}
                    className="mt-0.5 shrink-0"
                  />
                  <span className="text-[10px] leading-relaxed" style={{ color: '#8b949e' }}>
                    {esMenorDeEdad(form.fecha_nacimiento)
                      ? 'El padre, madre o tutor leyó y aceptó el '
                      : 'El socio leyó y aceptó el '}
                    <button type="button" onClick={() => setLeyendoAviso(true)}
                      className="font-semibold underline" style={{ color: '#22c55e' }}>
                      aviso de privacidad
                    </button>
                    {' '}(v{aviso.version}). Queda registrado con fecha y hora.
                  </span>
                </label>
              )}

              <div className="flex gap-3 pt-2">
                <button type="button" onClick={() => setModal(false)}
                  className="flex-1 py-2.5 rounded-lg text-xs font-semibold transition-colors"
                  style={{ border: '1px solid #21262d', color: '#8b949e', backgroundColor: 'transparent' }}>
                  Cancelar
                </button>
                <button type="submit" disabled={loading}
                  className="flex-1 py-2.5 rounded-lg text-xs font-bold transition-all disabled:opacity-50"
                  style={{ backgroundColor: '#22c55e', color: '#0d1117' }}>
                  {loading ? 'Guardando...' : 'Guardar'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Cancelación ARCO: irreversible y borra datos reales, por eso conserva la
          contraseña de autorización además de la palabra escrita. */}
      {cancelando && (
        <div className="fixed inset-0 flex items-center justify-center z-[70] p-4 overflow-y-auto" style={{ backgroundColor: 'rgba(0,0,0,0.85)' }}>
          <div className="rounded-2xl p-6 w-full max-w-sm my-auto max-h-[90vh] overflow-y-auto" style={CARD_STYLE}>
            <h2 className="text-sm font-bold text-white">Cancelar datos personales</h2>
            <p className="text-xs mt-2 leading-relaxed" style={{ color: '#8b949e' }}>
              Se borrarán nombre, contacto, fecha de nacimiento, sexo, foto y datos del
              tutor de{' '}
              <span className="text-white font-semibold">{cancelando.nombre} {cancelando.apellido}</span>.
              Su código QR dejará de abrir la puerta.
            </p>
            <p className="text-[10px] mt-2 leading-relaxed" style={{ color: '#8b949e' }}>
              Los pagos y las membresías se conservan anonimizados: la ley fiscal obliga
              a guardar la contabilidad cinco años. Ya no permitirán identificarlo.
            </p>
            <p className="text-[10px] mt-2 font-semibold" style={{ color: '#ef4444' }}>
              No se puede deshacer.
            </p>
            <form onSubmit={confirmarCancelacion} className="space-y-3 mt-4">
              <div>
                <label className="text-[10px] font-bold tracking-widest" style={{ color: '#8b949e' }}>
                  ESCRIBE <span style={{ color: '#ef4444' }}>CANCELAR</span> PARA CONFIRMAR
                </label>
                <input autoFocus autoComplete="off" value={cancelTexto}
                  onChange={e => { setCancelTexto(e.target.value); setCancelError('') }}
                  placeholder="cancelar"
                  className={inputCls} style={INPUT_STYLE} />
              </div>
              <div>
                <label className="text-[10px] font-bold tracking-widest" style={{ color: '#8b949e' }}>
                  CONTRASEÑA DE UN ADMINISTRADOR
                </label>
                <input type="password" required autoComplete="off" value={cancelPass}
                  onChange={e => { setCancelPass(e.target.value); setCancelError('') }}
                  className={inputCls} style={INPUT_STYLE} />
              </div>
              {cancelError && (
                <p className="text-[11px] font-semibold" style={{ color: '#ef4444' }}>{cancelError}</p>
              )}
              <div className="flex gap-3 pt-1">
                <button type="button" onClick={() => setCancelando(null)}
                  className="flex-1 py-2.5 rounded-lg text-xs font-semibold"
                  style={{ border: '1px solid #21262d', color: '#8b949e', backgroundColor: 'transparent' }}>
                  Cancelar
                </button>
                <button type="submit"
                  disabled={cancelLoading || !cancelPass || cancelTexto.trim().toLowerCase() !== 'cancelar'}
                  className="flex-1 py-2.5 rounded-lg text-xs font-bold disabled:opacity-40"
                  style={{ backgroundColor: '#ef4444', color: '#fff' }}>
                  {cancelLoading ? 'Borrando...' : 'Borrar datos'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {leyendoAviso && aviso && (
        <div className="fixed inset-0 flex items-center justify-center z-[70] p-4 overflow-y-auto" style={{ backgroundColor: 'rgba(0,0,0,0.85)' }}>
          <div className="rounded-2xl p-6 w-full max-w-2xl my-auto max-h-[90vh] overflow-y-auto" style={CARD_STYLE}>
            <div className="flex items-start justify-between gap-3 mb-4 sticky top-0 pb-3"
              style={{ backgroundColor: '#161b22', borderBottom: '1px solid #21262d' }}>
              <div>
                <h2 className="text-sm font-bold text-white">{aviso.titulo}</h2>
                <p className="text-[10px] mt-0.5" style={{ color: '#8b949e' }}>Versión {aviso.version}</p>
              </div>
              <button onClick={() => setLeyendoAviso(false)} style={{ color: '#8b949e' }} className="hover:text-white shrink-0">
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" /></svg>
              </button>
            </div>
            <Markdown texto={aviso.contenido} />
          </div>
        </div>
      )}

      {/* Autorización del dueño para mover la fecha de próximo pago */}
      {autorizacion && (
        <div className="fixed inset-0 flex items-center justify-center z-[60] p-4 overflow-y-auto" style={{ backgroundColor: 'rgba(0,0,0,0.8)' }}>
          <div className="rounded-2xl p-6 w-full max-w-sm my-auto max-h-[90vh] overflow-y-auto" style={CARD_STYLE}>
            <h2 className="text-sm font-bold text-white">Autorización requerida</h2>
            <p className="text-xs mt-2 leading-relaxed" style={{ color: '#8b949e' }}>
              Cambiar el próximo pago de <span className="text-white font-semibold">{autorizacion.socio}</span>
              {' '}de <span className="text-white">{autorizacion.de || '—'}</span>
              {' '}a <span style={{ color: '#f97316' }} className="font-semibold">{autorizacion.a}</span>.
            </p>
            <form onSubmit={confirmarAutorizacion} className="space-y-3 mt-4">
              <div>
                <label className="text-[10px] font-bold tracking-widest" style={{ color: '#8b949e' }}>
                  CONTRASEÑA DEL DUEÑO
                </label>
                <input
                  type="password" required autoFocus autoComplete="off"
                  value={authPass}
                  onChange={e => { setAuthPass(e.target.value); setAuthError('') }}
                  className={inputCls} style={INPUT_STYLE}
                />
              </div>
              <div>
                <label className="text-[10px] font-bold tracking-widest" style={{ color: '#8b949e' }}>
                  MOTIVO (OPCIONAL)
                </label>
                <input
                  value={authMotivo}
                  onChange={e => setAuthMotivo(e.target.value)}
                  placeholder="Ej. pagó en efectivo el viernes"
                  className={inputCls} style={INPUT_STYLE}
                />
              </div>
              {authError && (
                <p className="text-[11px] font-semibold" style={{ color: '#ef4444' }}>{authError}</p>
              )}
              <p className="text-[10px]" style={{ color: '#3d444d' }}>
                Queda registrado en la bitácora quién lo pidió y quién lo autorizó.
              </p>
              <div className="flex gap-3 pt-1">
                <button type="button" onClick={() => { setAutorizacion(null); setAuthPass('') }}
                  className="flex-1 py-2.5 rounded-lg text-xs font-semibold"
                  style={{ border: '1px solid #21262d', color: '#8b949e', backgroundColor: 'transparent' }}>
                  Cancelar
                </button>
                <button type="submit" disabled={authLoading || !authPass}
                  className="flex-1 py-2.5 rounded-lg text-xs font-bold disabled:opacity-40"
                  style={{ backgroundColor: '#f97316', color: '#0d1117' }}>
                  {authLoading ? 'Verificando...' : 'Autorizar'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {qrModal && (
        <div className="fixed inset-0 flex items-center justify-center z-50 p-4 overflow-y-auto" style={{ backgroundColor: 'rgba(0,0,0,0.7)' }}>
          <div className="rounded-2xl p-6 w-full max-w-sm text-center my-auto max-h-[90vh] overflow-y-auto" style={CARD_STYLE}>
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-sm font-bold text-white">Código QR de acceso</h2>
              <button onClick={() => setQrModal(null)} style={{ color: '#8b949e' }} className="hover:text-white">
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" /></svg>
              </button>
            </div>

            <p className="text-xs mb-4" style={{ color: '#8b949e' }}>
              {qrModal.nombre} {qrModal.apellido}
            </p>

            {qrModal.codigo_acceso ? (
              <>
                <div className="flex items-center justify-center mb-4">
                  {/* Fondo blanco a propósito: un QR sobre el panel oscuro no lo lee ningún escáner. */}
                  <div className="p-3 rounded-xl" style={{ backgroundColor: '#fff' }}>
                    <QRCodeSVG id="qr-socio" value={qrModal.codigo_acceso} size={168} level="M" />
                  </div>
                </div>
                <button
                  onClick={() => { navigator.clipboard.writeText(qrModal.codigo_acceso); toast.success('Código copiado') }}
                  title="Clic para copiar"
                  className="text-[11px] font-mono px-2 py-1 rounded mb-5 inline-block transition-opacity hover:opacity-70"
                  style={{ backgroundColor: 'rgba(34,197,94,0.08)', color: '#22c55e', border: '1px solid rgba(34,197,94,0.25)' }}
                >
                  {qrModal.codigo_acceso}
                </button>
                <div className="flex gap-3">
                  <button
                    onClick={() => setQrModal(null)}
                    className="flex-1 py-2.5 rounded-lg text-xs font-semibold"
                    style={{ border: '1px solid #21262d', color: '#8b949e', backgroundColor: 'transparent' }}
                  >
                    Cerrar
                  </button>
                  <button
                    onClick={imprimirQR}
                    className="flex-1 py-2.5 rounded-lg text-xs font-bold"
                    style={{ backgroundColor: '#22c55e', color: '#0d1117' }}
                  >
                    Imprimir
                  </button>
                </div>
              </>
            ) : (
              <>
                <div className="flex items-center justify-center mb-4">
                  <div className="w-20 h-20 rounded-full flex items-center justify-center"
                    style={{ backgroundColor: 'rgba(139,148,158,0.1)' }}>
                    <svg className="w-9 h-9" fill="none" stroke="currentColor" viewBox="0 0 24 24" style={{ color: '#8b949e' }}>
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 4h6v6H4V4zm10 0h6v6h-6V4zM4 14h6v6H4v-6zm10 4h2m-2 2h6m0-6v2m0 0h-4" />
                    </svg>
                  </div>
                </div>
                <p className="text-xs mb-5" style={{ color: '#8b949e' }}>
                  Este socio todavía no tiene código de acceso.
                </p>
                <button
                  onClick={asignarQR}
                  disabled={qrLoading}
                  className="w-full py-2.5 rounded-lg text-xs font-bold transition-all disabled:opacity-50"
                  style={{ backgroundColor: '#22c55e', color: '#0d1117' }}
                >
                  {qrLoading ? 'Asignando...' : 'Asignar código QR'}
                </button>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

function vencePronto(fecha) {
  if (!fecha) return false
  const d = new Date(fecha)
  const hoy = new Date()
  const diff = (d - hoy) / (1000 * 60 * 60 * 24)
  return diff <= 3
}
