import { useState } from 'react'
import toast from 'react-hot-toast'

const CARD_STYLE = { backgroundColor: '#161b22', border: '1px solid #21262d' }
const INPUT_STYLE = {
  backgroundColor: '#0d1117', border: '1px solid #21262d', color: '#fff',
  borderRadius: '8px', padding: '10px 12px', fontSize: '14px', width: '100%', outline: 'none',
}

function Toggle({ value, onChange }) {
  return (
    <button
      type="button"
      onClick={() => onChange(!value)}
      className="relative w-11 h-6 rounded-full transition-colors duration-200 shrink-0"
      style={{ backgroundColor: value ? '#22c55e' : '#21262d' }}
    >
      <span
        className="absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full shadow transition-transform duration-200"
        style={{ transform: value ? 'translateX(20px)' : 'translateX(0)' }}
      />
    </button>
  )
}

export default function Configuracion() {
  const [gym, setGym] = useState({
    nombre: 'Round3Boxing',
    direccion: 'Av. Principal 420, Col. Centro',
    telefono: '+52 55 1234 5678',
    email: 'admin@round3boxing.com',
    horario: 'Lun-Vie 05:30-22:00 · Sáb 07:00-18:00 · Dom 08:00-14:00',
  })

  const [notif, setNotif] = useState({
    pagos_vencidos: true,
    reporte_diario: false,
    mantenimiento: true,
    reporte_semanal: true,
  })

  const guardar = e => {
    e.preventDefault()
    toast.success('Configuración guardada')
  }

  const plan = { nombre: 'Socio Regular', precio: 499, descripcion: 'Acceso mensual completo' }

  return (
    <div className="space-y-5">
      <h2 className="text-xl font-black text-white uppercase tracking-wide">CONFIGURACIÓN</h2>
      <p className="text-xs -mt-3" style={{ color: '#8b949e' }}>Administración del sistema</p>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        {/* Gym info */}
        <div className="rounded-xl p-6" style={CARD_STYLE}>
          <div className="flex items-center gap-2 mb-5">
            <svg className="w-4 h-4 text-[#22c55e]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
            </svg>
            <h3 className="text-sm font-bold text-white">Información del Gym</h3>
          </div>
          <form onSubmit={guardar} className="space-y-4">
            {[
              { key: 'nombre', label: 'NOMBRE DEL NEGOCIO', icon: 'M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z' },
              { key: 'direccion', label: 'DIRECCIÓN', icon: 'M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z' },
              { key: 'telefono', label: 'TELÉFONO', icon: 'M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21l-2.257 1.13a11.042 11.042 0 005.516 5.516l1.13-2.257a1 1 0 011.21-.502l4.493 1.498a1 1 0 01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z' },
              { key: 'email', label: 'CORREO ELECTRÓNICO', icon: 'M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z' },
              { key: 'horario', label: 'HORARIO DE ATENCIÓN', icon: 'M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z' },
            ].map(f => (
              <div key={f.key}>
                <label className="text-[10px] font-bold tracking-widest block mb-1.5" style={{ color: '#8b949e' }}>{f.label}</label>
                <div className="flex items-center gap-2 px-3 py-2.5 rounded-lg" style={{ backgroundColor: '#0d1117', border: '1px solid #21262d' }}>
                  <svg className="w-4 h-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" style={{ color: '#8b949e' }}>
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d={f.icon} />
                  </svg>
                  <input
                    value={gym[f.key]}
                    onChange={e => setGym(g => ({ ...g, [f.key]: e.target.value }))}
                    className="bg-transparent text-white text-sm w-full outline-none"
                  />
                </div>
              </div>
            ))}
            <button
              type="submit"
              className="w-full py-3 rounded-lg text-sm font-bold flex items-center justify-center gap-2 mt-2"
              style={{ backgroundColor: '#22c55e', color: '#0d1117' }}
              onMouseEnter={e => e.currentTarget.style.backgroundColor = '#16a34a'}
              onMouseLeave={e => e.currentTarget.style.backgroundColor = '#22c55e'}
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7H5a2 2 0 00-2 2v9a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-3m-1 4l-3 3m0 0l-3-3m3 3V4" />
              </svg>
              Guardar cambios
            </button>
          </form>
        </div>

        {/* Right column */}
        <div className="space-y-4">
          {/* Notificaciones */}
          <div className="rounded-xl p-6" style={CARD_STYLE}>
            <div className="flex items-center gap-2 mb-4">
              <svg className="w-4 h-4 text-[#3b82f6]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
              </svg>
              <h3 className="text-sm font-bold text-white">Notificaciones</h3>
            </div>
            <div className="space-y-4">
              {[
                { key: 'pagos_vencidos', label: 'Alertas de pagos vencidos' },
                { key: 'reporte_diario', label: 'Reporte diario de asistencia' },
                { key: 'mantenimiento', label: 'Alertas de mantenimiento' },
                { key: 'reporte_semanal', label: 'Reporte semanal automático' },
              ].map(n => (
                <div key={n.key} className="flex items-center justify-between">
                  <span className="text-sm" style={{ color: '#8b949e' }}>{n.label}</span>
                  <Toggle value={notif[n.key]} onChange={v => setNotif(p => ({ ...p, [n.key]: v }))} />
                </div>
              ))}
            </div>
          </div>

          {/* Datos y backup */}
          <div className="rounded-xl p-6" style={CARD_STYLE}>
            <div className="flex items-center gap-2 mb-4">
              <svg className="w-4 h-4 text-[#a855f7]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4" />
              </svg>
              <h3 className="text-sm font-bold text-white">Datos y Backup</h3>
            </div>
            <button className="flex items-center gap-2 text-sm mb-3 hover:opacity-80 transition-opacity" style={{ color: '#22c55e' }}>
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
              </svg>
              Exportar todos los datos
            </button>
            <div className="flex items-center gap-2 text-sm mb-1" style={{ color: '#3b82f6' }}>
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4" />
              </svg>
              Backup automático · Activo
            </div>
            <p className="text-[10px]" style={{ color: '#3d444d' }}>Último backup: Hoy 04:00am · Siguiente: Mañana 04:00am</p>
          </div>
        </div>
      </div>

      {/* Planes */}
      <div className="rounded-xl p-6" style={CARD_STYLE}>
        <div className="flex items-center justify-between mb-5">
          <div className="flex items-center gap-2">
            <svg className="w-4 h-4 text-[#f97316]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 10h18M7 15h1m4 0h1m-7 4h12a3 3 0 003-3V8a3 3 0 00-3-3H6a3 3 0 00-3 3v8a3 3 0 003 3z" />
            </svg>
            <div>
              <h3 className="text-sm font-bold text-white">Planes y Precios</h3>
              <p className="text-[10px]" style={{ color: '#8b949e' }}>Editar membresías</p>
            </div>
          </div>
        </div>
        <div className="rounded-xl p-5" style={{ backgroundColor: '#0d1117', border: '1px solid #21262d' }}>
          <div className="flex items-center justify-between gap-3 flex-wrap">
            <div>
              <p className="text-sm font-bold text-white">{plan.nombre}</p>
              <p className="text-[10px] mt-0.5" style={{ color: '#8b949e' }}>{plan.descripcion}</p>
            </div>
            <div className="flex items-center gap-4">
              <p className="text-2xl font-black text-white">
                <span style={{ color: '#22c55e' }}>${plan.precio}</span>
                <span className="text-xs font-normal ml-1" style={{ color: '#8b949e' }}>/mes</span>
              </p>
              <button style={{ color: '#8b949e' }} className="hover:text-white transition-colors">
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                </svg>
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
