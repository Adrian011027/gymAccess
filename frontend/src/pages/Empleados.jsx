import { useEffect, useState } from 'react'
import toast from 'react-hot-toast'
import api from '../api/axios'

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

export default function Empleados() {
  const [sucursales, setSucursales] = useState([])
  const [usuarios, setUsuarios] = useState([])
  const [gymReal, setGymReal] = useState(null)
  const [userModal, setUserModal] = useState(false)
  const [userForm, setUserForm] = useState(USER_EMPTY)
  const [guardando, setGuardando] = useState(false)

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

  const abrirNuevo = () => { setUserForm(USER_EMPTY); setUserModal(true) }

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
        <div className="space-y-2">
          {usuarios.map(u => (
            <div key={u.id} className="flex items-center justify-between rounded-lg px-4 py-3 flex-wrap gap-2"
              style={{ backgroundColor: '#0d1117', border: '1px solid #21262d' }}>
              <div className="min-w-0">
                <p className="text-xs font-bold text-white truncate">{u.nombre}</p>
                <p className="text-[10px] truncate" style={{ color: '#8b949e' }}>{u.email}</p>
              </div>
              <div className="flex items-center gap-3 shrink-0">
                <span className="text-[10px] capitalize" style={{ color: '#8b949e' }}>{u.rol}</span>
                <span className="text-[10px] font-semibold" style={{ color: u.sucursales_permitidas?.length ? '#f97316' : '#22c55e' }}>
                  {u.sucursales_permitidas?.length
                    ? sucursales.filter(s => u.sucursales_permitidas.includes(s.id)).map(s => s.nombre).join(', ')
                    : 'Todas'}
                </span>
                <button onClick={() => abrirEditar(u)}
                  className="text-[10px] font-semibold" style={{ color: '#8b949e' }}>
                  Editar
                </button>
              </div>
            </div>
          ))}
          {usuarios.length === 0 && (
            <p className="text-xs text-center py-4" style={{ color: '#3d444d' }}>Sin empleados</p>
          )}
        </div>
      </div>

      {userModal && (
        <div className="fixed inset-0 flex items-center justify-center z-50 p-4 overflow-y-auto" style={{ backgroundColor: 'rgba(0,0,0,0.7)' }}>
          <div className="rounded-2xl p-6 w-full max-w-lg my-8" style={CARD_STYLE}>
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
                  onChange={e => setUserForm(f => ({ ...f, rol: e.target.value }))}
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
                {userForm.sucursales_permitidas.length === 0 && (
                  <p className="text-[10px] mt-1.5" style={{ color: '#f97316' }}>
                    ⚠ Sin sucursales, este empleado verá los datos de todo el negocio.
                  </p>
                )}
              </div>

              {userForm.sucursales_permitidas.length > 0 && (
                <div>
                  <label className="text-[10px] font-bold tracking-widest" style={{ color: '#8b949e' }}>
                    SUCURSAL ACTIVA {userForm.sucursales_permitidas.length >= 2 && '(se puede cambiar al elegir en el login)'}
                  </label>
                  <select value={userForm.sucursal || ''}
                    onChange={e => setUserForm(f => ({ ...f, sucursal: e.target.value }))}
                    className="mt-1" style={INPUT_STYLE}>
                    <option value="">Sin elegir todavía</option>
                    {sucursales.filter(s => userForm.sucursales_permitidas.includes(s.id)).map(s => (
                      <option key={s.id} value={s.id}>{s.nombre}</option>
                    ))}
                  </select>
                </div>
              )}

              {userForm.sucursales_permitidas.length > 0 && (
                <div>
                  <label className="text-[10px] font-bold tracking-widest" style={{ color: '#8b949e' }}>
                    HORARIO (informativo)
                  </label>
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
                          <option value="">Libre</option>
                          {sucursales.filter(s => userForm.sucursales_permitidas.includes(s.id)).map(s => (
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
