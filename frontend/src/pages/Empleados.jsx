import { useEffect, useState } from 'react'
import toast from 'react-hot-toast'
import api from '../api/axios'
import { useAuth } from '../context/AuthContext'

const CARD_STYLE = { backgroundColor: '#161b22', border: '1px solid #21262d' }
const INPUT_STYLE = {
  backgroundColor: '#0d1117', border: '1px solid #21262d', color: '#fff',
  borderRadius: '8px', padding: '10px 12px', fontSize: '14px', width: '100%', outline: 'none',
}

const DIAS = [
  ['lunes', 'Lunes'], ['martes', 'Martes'], ['miercoles', 'Miércoles'], ['jueves', 'Jueves'],
  ['viernes', 'Viernes'], ['sabado', 'Sábado'], ['domingo', 'Domingo'],
]

const USER_EMPTY = {
  nombre: '', email: '', rol: 'recepcion', sucursal: '', password: '',
  sucursales_permitidas: [], horario_semanal: {},
}

// Etiquetas de los roles de `Usuario.ROL_CHOICES`. Un rol que se agregue en el
// backend sigue apareciendo en el filtro por su clave cruda, no se pierde.
const ROLES = {
  superadmin: 'Super admin', admin: 'Admin', recepcion: 'Recepción', coach: 'Coach',
}

export default function Empleados() {
  const { user } = useAuth()
  const [sucursales, setSucursales] = useState([])
  const [usuarios, setUsuarios] = useState([])
  const [gymReal, setGymReal] = useState(null)
  const [userModal, setUserModal] = useState(false)
  const [userForm, setUserForm] = useState(USER_EMPTY)
  const [guardando, setGuardando] = useState(false)
  // Dar de baja a alguien no se deshace desde la interfaz, así que se pide escribir
  // la palabra: un clic de más en el botón equivocado no debe bastar.
  const [baja, setBaja] = useState(null)
  const [bajaTexto, setBajaTexto] = useState('')
  const [bajaError, setBajaError] = useState('')
  const [bajaLoading, setBajaLoading] = useState(false)
  const [filtroRol, setFiltroRol] = useState('todos')

  const cargarSucursales = () => api.get('/gyms/sucursales/').then(r => setSucursales(r.data)).catch(() => {})
  const cargarUsuarios = () => api.get('/usuarios/').then(r => setUsuarios(r.data)).catch(() => {})
  const cargarGym = () => api.get('/gyms/').then(r => setGymReal(r.data[0] || null)).catch(() => {})

  useEffect(() => {
    cargarSucursales()
    cargarUsuarios()
    cargarGym()
  }, [])

  const errorDe = err => {
    const d = err.response?.data
    if (typeof d === 'object' && d) return Object.values(d).flat()[0]
    return 'No se pudo guardar'
  }

  // Solo se ofrecen los roles que existen en la plantilla: una pestaña que siempre
  // da vacío es ruido, y el conteo delata de inmediato si falta cubrir un puesto.
  const rolesPresentes = [...new Set(usuarios.map(u => u.rol))].sort()
  const visibles = filtroRol === 'todos' ? usuarios : usuarios.filter(u => u.rol === filtroRol)

  const abrirNuevo = () => { setUserForm(USER_EMPTY); setUserModal(true) }

  const abrirBaja = u => {
    setBaja(u)
    setBajaTexto('')
    setBajaError('')
  }

  const confirmarBaja = async e => {
    e.preventDefault()
    if (bajaTexto.trim().toLowerCase() !== 'eliminar') {
      setBajaError('Escribe exactamente "eliminar" para confirmar.')
      return
    }
    setBajaLoading(true)
    setBajaError('')
    try {
      await api.delete(`/usuarios/${baja.id}/`)
      toast.success(`${baja.nombre} fue dado de baja`)
      setBaja(null)
      cargarUsuarios()
    } catch (err) {
      setBajaError(err.response?.data?.detail || errorDe(err))
    } finally {
      setBajaLoading(false)
    }
  }

  const abrirEditar = u => {
    setUserForm({
      ...u,
      password: '',
      sucursal: u.sucursal || '',
      sucursales_permitidas: u.sucursales_permitidas || [],
      horario_semanal: u.horario_semanal || {},
    })
    setUserModal(true)
  }

  // El dueño (admin) opera el negocio entero: sucursal nula es su valor correcto,
  // no un olvido. Para el resto es obligatoria.
  const esAdmin = userForm.rol === 'admin'
  // Si marcó permitidas, la activa sale de ahí; si no marcó ninguna, de todas.
  const opcionesSucursal = userForm.sucursales_permitidas.length
    ? sucursales.filter(s => userForm.sucursales_permitidas.includes(s.id))
    : sucursales

  const toggleSucursal = id => {
    setUserForm(f => {
      const activa = f.sucursales_permitidas.includes(id)
      const permitidas = activa
        ? f.sucursales_permitidas.filter(x => x !== id)
        : [...f.sucursales_permitidas, id]
      // Si se destildó la que estaba activa, o si aún no hay activa, se limpia/ajusta.
      const sucursal = permitidas.includes(Number(f.sucursal)) ? f.sucursal : ''
      return { ...f, sucursales_permitidas: permitidas, sucursal }
    })
  }

  const setDiaHorario = (dia, sucursalId) => {
    setUserForm(f => ({
      ...f,
      horario_semanal: { ...f.horario_semanal, [dia]: sucursalId || null },
    }))
  }

  const guardarUsuario = async e => {
    e.preventDefault()
    setGuardando(true)
    try {
      const payload = {
        ...userForm,
        gym: gymReal?.id,
        sucursal: userForm.sucursal || null,
      }
      if (!payload.password) delete payload.password
      if (userForm.id) await api.patch(`/usuarios/${userForm.id}/`, payload)
      else await api.post('/usuarios/', payload)
      toast.success('Empleado guardado')
      setUserModal(false)
      setUserForm(USER_EMPTY)
      cargarUsuarios()
    } catch (err) { toast.error(errorDe(err)) } finally { setGuardando(false) }
  }

  return (
    <div className="space-y-5">
      <h2 className="text-xl font-black text-white uppercase tracking-wide">EMPLEADOS</h2>
      <p className="text-xs -mt-3" style={{ color: '#8b949e' }}>
        Sucursales asignadas y horario de referencia de cada empleado
      </p>

      <div className="rounded-xl p-6" style={CARD_STYLE}>
        <div className="flex items-center justify-between mb-5 flex-wrap gap-3">
          <div>
            <h3 className="text-sm font-bold text-white">Personal</h3>
            <p className="text-[10px]" style={{ color: '#8b949e' }}>
              Con 2+ sucursales permitidas, el empleado elige con cuál entra al iniciar sesión
            </p>
          </div>
          <button
            onClick={abrirNuevo}
            className="px-4 py-2 rounded-lg text-xs font-bold"
            style={{ backgroundColor: '#22c55e', color: '#0d1117' }}
          >
            + Nuevo empleado
          </button>
        </div>
        <div className="flex flex-wrap gap-2 mb-3">
          {[['todos', 'Todos'], ...rolesPresentes.map(r => [r, ROLES[r] ?? r])].map(([clave, etiqueta]) => {
            const n = clave === 'todos' ? usuarios.length : usuarios.filter(u => u.rol === clave).length
            const activo = filtroRol === clave
            return (
              <button
                key={clave}
                onClick={() => setFiltroRol(clave)}
                className="px-3 py-1.5 rounded-lg text-[10px] font-bold tracking-wide transition-colors"
                style={{
                  backgroundColor: activo ? '#22c55e' : '#0d1117',
                  color: activo ? '#0d1117' : '#8b949e',
                  border: `1px solid ${activo ? '#22c55e' : '#21262d'}`,
                }}
              >
                {etiqueta} <span style={{ opacity: 0.7 }}>{n}</span>
              </button>
            )
          })}
        </div>
        <div className="space-y-2">
          {visibles.map(u => (
            <div key={u.id} className="flex items-center justify-between rounded-lg px-4 py-3 flex-wrap gap-2"
              style={{ backgroundColor: '#0d1117', border: '1px solid #21262d' }}>
              <div className="min-w-0">
                <p className="text-xs font-bold text-white truncate">{u.nombre}</p>
                <p className="text-[10px] truncate" style={{ color: '#8b949e' }}>{u.email}</p>
              </div>
              <div className="flex items-center gap-3 shrink-0">
                <span className="text-[10px]" style={{ color: '#8b949e' }}>{ROLES[u.rol] ?? u.rol}</span>
                <span className="text-[10px] font-semibold" style={{ color: u.sucursales_permitidas?.length ? '#f97316' : '#22c55e' }}>
                  {u.sucursales_permitidas?.length
                    ? sucursales.filter(s => u.sucursales_permitidas.includes(s.id)).map(s => s.nombre).join(', ')
                    : 'Todas'}
                </span>
                <button onClick={() => abrirEditar(u)}
                  className="text-[10px] font-semibold hover:text-white transition-colors"
                  style={{ color: '#8b949e' }}>
                  Editar
                </button>
                {/* Uno no puede darse de baja a sí mismo: se oculta en vez de
                    dejar que lo intente y reciba un error. */}
                {String(u.id) !== String(user?.user_id) && (
                  <button onClick={() => abrirBaja(u)}
                    title="Dar de baja"
                    className="text-[10px] font-semibold transition-colors"
                    style={{ color: '#8b949e' }}
                    onMouseEnter={e => e.currentTarget.style.color = '#ef4444'}
                    onMouseLeave={e => e.currentTarget.style.color = '#8b949e'}>
                    Eliminar
                  </button>
                )}
              </div>
            </div>
          ))}
          {visibles.length === 0 && (
            <p className="text-xs text-center py-4" style={{ color: '#3d444d' }}>
              {usuarios.length === 0 ? 'Sin empleados' : `Ningún empleado con rol ${ROLES[filtroRol] ?? filtroRol}`}
            </p>
          )}
        </div>
      </div>

      {baja && (
        <div className="fixed inset-0 flex items-center justify-center z-[60] p-4 overflow-y-auto" style={{ backgroundColor: 'rgba(0,0,0,0.8)' }}>
          <div className="rounded-2xl p-6 w-full max-w-sm my-auto max-h-[90vh] overflow-y-auto" style={CARD_STYLE}>
            <h2 className="text-sm font-bold text-white">Dar de baja a un empleado</h2>
            <p className="text-xs mt-2 leading-relaxed" style={{ color: '#8b949e' }}>
              <span className="text-white font-semibold">{baja.nombre}</span> dejará de
              poder iniciar sesión de inmediato.
            </p>
            <p className="text-[10px] mt-2 leading-relaxed" style={{ color: '#8b949e' }}>
              Su historial no se borra: los pagos que cobró y las autorizaciones que dio
              siguen registrados a su nombre, o la bitácora se quedaría sin responsable.
            </p>
            <form onSubmit={confirmarBaja} className="space-y-3 mt-4">
              <div>
                <label className="text-[10px] font-bold tracking-widest" style={{ color: '#8b949e' }}>
                  ESCRIBE <span style={{ color: '#ef4444' }}>ELIMINAR</span> PARA CONFIRMAR
                </label>
                <input
                  autoFocus autoComplete="off"
                  value={bajaTexto}
                  onChange={e => { setBajaTexto(e.target.value); setBajaError('') }}
                  placeholder="eliminar"
                  className="mt-1" style={INPUT_STYLE}
                />
              </div>
              {bajaError && (
                <p className="text-[11px] font-semibold" style={{ color: '#ef4444' }}>{bajaError}</p>
              )}
              <div className="flex gap-3 pt-1">
                <button type="button" onClick={() => setBaja(null)}
                  className="flex-1 py-2.5 rounded-lg text-xs font-semibold"
                  style={{ border: '1px solid #21262d', color: '#8b949e', backgroundColor: 'transparent' }}>
                  Cancelar
                </button>
                <button type="submit"
                  disabled={bajaLoading || bajaTexto.trim().toLowerCase() !== 'eliminar'}
                  className="flex-1 py-2.5 rounded-lg text-xs font-bold disabled:opacity-40"
                  style={{ backgroundColor: '#ef4444', color: '#fff' }}>
                  {bajaLoading ? 'Dando de baja...' : 'Eliminar'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {userModal && (
        <div className="fixed inset-0 flex items-center justify-center z-50 p-4 overflow-y-auto" style={{ backgroundColor: 'rgba(0,0,0,0.7)' }}>
          <div className="rounded-2xl p-6 w-full max-w-lg my-auto max-h-[90vh] overflow-y-auto" style={CARD_STYLE}>
            <h2 className="text-sm font-bold text-white mb-5">
              {userForm.id ? 'Editar empleado' : 'Nuevo empleado'}
            </h2>
            <form onSubmit={guardarUsuario} className="space-y-3">
              <div>
                <label className="text-[10px] font-bold tracking-widest" style={{ color: '#8b949e' }}>NOMBRE</label>
                <input required value={userForm.nombre}
                  onChange={e => setUserForm(f => ({ ...f, nombre: e.target.value }))}
                  className="mt-1" style={INPUT_STYLE} />
              </div>
              <div>
                <label className="text-[10px] font-bold tracking-widest" style={{ color: '#8b949e' }}>EMAIL</label>
                <input required type="email" value={userForm.email}
                  onChange={e => setUserForm(f => ({ ...f, email: e.target.value }))}
                  className="mt-1" style={INPUT_STYLE} />
              </div>
              <div>
                <label className="text-[10px] font-bold tracking-widest" style={{ color: '#8b949e' }}>ROL</label>
                <select value={userForm.rol}
                  onChange={e => setUserForm(f => ({
                    ...f, rol: e.target.value,
                    // Un admin no se ata a una sucursal: si se cambia el rol a admin
                    // se limpia, o quedaría viendo solo un local sin motivo.
                    sucursal: e.target.value === 'admin' ? '' : f.sucursal,
                  }))}
                  className="mt-1" style={INPUT_STYLE}>
                  <option value="recepcion">Recepción</option>
                  <option value="coach">Coach</option>
                  <option value="admin">Admin</option>
                </select>
              </div>

              <div>
                <label className="text-[10px] font-bold tracking-widest" style={{ color: '#8b949e' }}>
                  SUCURSALES PERMITIDAS
                </label>
                <div className="mt-1.5 flex flex-wrap gap-2">
                  {sucursales.map(s => (
                    <label key={s.id}
                      className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg cursor-pointer text-xs"
                      style={{
                        border: '1px solid #21262d',
                        backgroundColor: userForm.sucursales_permitidas.includes(s.id) ? 'rgba(34,197,94,0.12)' : 'transparent',
                        color: userForm.sucursales_permitidas.includes(s.id) ? '#22c55e' : '#8b949e',
                      }}>
                      <input type="checkbox"
                        checked={userForm.sucursales_permitidas.includes(s.id)}
                        onChange={() => toggleSucursal(s.id)} />
                      {s.nombre}
                    </label>
                  ))}
                </div>
                <p className="text-[10px] mt-1.5" style={{ color: '#8b949e' }}>
                  {userForm.sucursales_permitidas.length === 0
                    ? 'Sin marcar ninguna, podrá elegir entre todas las sucursales.'
                    : 'Entre estas podrá rotar al iniciar sesión.'}
                </p>
              </div>

              {/* Siempre visible: antes solo aparecía si ya había permitidas marcadas,
                  así que era fácil guardar a recepción sin sucursal — y sin sucursal
                  ve los datos de todo el negocio. */}
              {esAdmin || (
                <div>
                  <label className="text-[10px] font-bold tracking-widest" style={{ color: '#8b949e' }}>
                    SUCURSAL ACTIVA (EN LA QUE ESTÁ TRABAJANDO AHORA) <span style={{ color: '#f97316' }}>*</span>
                  </label>
                  <select required value={userForm.sucursal || ''}
                    onChange={e => setUserForm(f => ({ ...f, sucursal: e.target.value }))}
                    className="mt-1" style={INPUT_STYLE}>
                    <option value="">Selecciona una sucursal</option>
                    {opcionesSucursal.map(s => (
                      <option key={s.id} value={s.id}>{s.nombre}</option>
                    ))}
                  </select>
                  <p className="text-[10px] mt-1.5 leading-relaxed" style={{ color: '#8b949e' }}>
                    Es el local desde el que ve y registra datos ahora mismo: socios, caja,
                    inventario y accesos son los de esta sucursal, no los de las otras.
                    {userForm.sucursales_permitidas.length >= 2
                      ? ' Como tiene varias permitidas, la cambia él mismo al iniciar sesión; aquí solo se deja preseleccionada.'
                      : ' Con una sola sucursal permitida, siempre es esa.'}
                  </p>
                </div>
              )}

              {!esAdmin && (
                <div>
                  <label className="text-[10px] font-bold tracking-widest" style={{ color: '#8b949e' }}>
                    HORARIO SEMANAL (INFORMATIVO)
                  </label>
                  <p className="text-[10px] mt-1 leading-relaxed" style={{ color: '#8b949e' }}>
                    En qué sucursal le toca cada día. Es solo una referencia para el
                    admin: no bloquea el acceso ni cambia la sucursal activa.
                  </p>
                  <div className="rounded-lg overflow-hidden mt-1.5" style={{ border: '1px solid #21262d' }}>
                    {DIAS.map(([k, label], i) => (
                      <div key={k} className="flex items-center gap-2 px-3 py-2"
                        style={{ backgroundColor: '#0d1117', borderTop: i ? '1px solid #21262d' : undefined }}>
                        <span className="text-xs w-20 shrink-0" style={{ color: '#8b949e' }}>{label}</span>
                        <select
                          value={userForm.horario_semanal[k] ?? ''}
                          onChange={e => setDiaHorario(k, e.target.value)}
                          className="flex-1 text-xs px-2 py-1 rounded bg-transparent text-white outline-none"
                          style={{ border: '1px solid #21262d' }}
                        >
                          <option value="">Descanso — no trabaja</option>
                          {opcionesSucursal.map(s => (
                            <option key={s.id} value={s.id}>{s.nombre}</option>
                          ))}
                        </select>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              <div>
                <label className="text-[10px] font-bold tracking-widest" style={{ color: '#8b949e' }}>
                  CONTRASEÑA {userForm.id && '(dejar vacío para no cambiarla)'}
                </label>
                <input type="password" autoComplete="new-password" required={!userForm.id}
                  value={userForm.password}
                  onChange={e => setUserForm(f => ({ ...f, password: e.target.value }))}
                  className="mt-1" style={INPUT_STYLE} />
              </div>
              <div className="flex gap-3 pt-2">
                <button type="button" onClick={() => setUserModal(false)}
                  className="flex-1 py-2.5 rounded-lg text-xs font-semibold"
                  style={{ border: '1px solid #21262d', color: '#8b949e', backgroundColor: 'transparent' }}>
                  Cancelar
                </button>
                <button type="submit" disabled={guardando}
                  className="flex-1 py-2.5 rounded-lg text-xs font-bold disabled:opacity-50"
                  style={{ backgroundColor: '#22c55e', color: '#0d1117' }}>
                  {guardando ? 'Guardando...' : 'Guardar'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
