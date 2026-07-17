import { useEffect, useState } from 'react'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts'
import api from '../api/axios'

const CARD_STYLE = { backgroundColor: '#161b22', border: '1px solid #21262d' }

const HORAS_MOCK = [
  { hora: '5am', v: 12 }, { hora: '6am', v: 28 }, { hora: '7am', v: 45 }, { hora: '8am', v: 98 },
  { hora: '9am', v: 70 }, { hora: '10am', v: 62 }, { hora: '11am', v: 55 }, { hora: '12pm', v: 40 },
  { hora: '1pm', v: 35 }, { hora: '2pm', v: 30 }, { hora: '3pm', v: 38 }, { hora: '4pm', v: 58 },
  { hora: '5pm', v: 120 }, { hora: '6pm', v: 135 }, { hora: '7pm', v: 110 }, { hora: '8pm', v: 90 },
  { hora: '9pm', v: 45 },
]

const PAGOS_MOCK = [
  { id: 1, nombre: 'Carlos Mendoza', plan: 'Socio Regular', monto: 499, vence: '2025-07-05' },
  { id: 2, nombre: 'Sofía Ramírez', plan: 'Socio Regular', monto: 499, vence: '2025-07-03' },
  { id: 3, nombre: 'Rodrigo Quispe', plan: 'Socio Regular', monto: 499, vence: '2025-07-03' },
]

const CLASES_HOY_MOCK = [
  { nombre: 'Preparación Física', tipo: 'fisico', hora: '06:00-07:00', profesor: 'Miguel R.', ocupacion: 8, cupo: 16, estado: 'Completada' },
  { nombre: 'Combinaciones', tipo: 'combinaciones', hora: '07:00-08:00', profesor: 'Miguel R.', ocupacion: 12, cupo: 15, estado: 'Completada' },
  { nombre: 'Defensa', tipo: 'defensa', hora: '18:00-19:00', profesor: 'Daniela T.', ocupacion: 17, cupo: 20, estado: 'En curso' },
  { nombre: 'Sparring', tipo: 'sparring', hora: '19:00-20:30', profesor: 'Laura V.', ocupacion: 6, cupo: 10, estado: 'Próxima' },
]

const ESTADO_COLORS = {
  'Completada': '#8b949e',
  'En curso': '#22c55e',
  'Próxima': '#3b82f6',
}

function initials(name) {
  return name.split(' ').slice(0, 2).map(w => w[0]).join('').toUpperCase()
}

const AVATAR_COLORS = ['#f97316', '#a855f7', '#3b82f6', '#22c55e', '#ef4444', '#eab308']
function avatarColor(name) { return AVATAR_COLORS[name.charCodeAt(0) % AVATAR_COLORS.length] }

export default function Dashboard() {
  const [socios, setSocios] = useState([])
  const [accesos, setAccesos] = useState(null)

  useEffect(() => {
    api.get('/socios/').then(r => setSocios(r.data)).catch(() => {})
    api.get('/accesos/stats/').then(r => setAccesos(r.data)).catch(() => {})
  }, [])

  const sociosActivos = socios.filter(s => s.activo).length

  const CustomTooltip = ({ active, payload, label }) => {
    if (!active || !payload?.length) return null
    const v = payload[0].value
    const color = v >= 85 ? '#22c55e' : v >= 50 ? '#86efac' : '#4ade80'
    return (
      <div className="px-3 py-2 rounded-lg text-xs" style={{ backgroundColor: '#1c2333', border: '1px solid #21262d', color: '#fff' }}>
        <p className="font-bold">{label}</p>
        <p style={{ color }}>{v} visitantes</p>
      </div>
    )
  }

  return (
    <div className="space-y-5">
      {/* Stat cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="rounded-xl p-5 flex items-center gap-4" style={CARD_STYLE}>
          <div className="w-10 h-10 rounded-full flex items-center justify-center shrink-0" style={{ backgroundColor: 'rgba(34,197,94,0.1)' }}>
            <svg className="w-5 h-5 text-[#22c55e]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z" />
            </svg>
          </div>
          <div>
            <p className="text-3xl font-black text-white">{sociosActivos || '—'}</p>
            <p className="text-xs mt-0.5" style={{ color: '#8b949e' }}>Socios Activos</p>
            <p className="text-xs mt-0.5 text-[#22c55e]">+8 hoy</p>
          </div>
        </div>

        <div className="rounded-xl p-5 flex items-center gap-4" style={CARD_STYLE}>
          <div className="w-10 h-10 rounded-full flex items-center justify-center shrink-0" style={{ backgroundColor: 'rgba(59,130,246,0.1)' }}>
            <svg className="w-5 h-5 text-[#3b82f6]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
            </svg>
          </div>
          <div>
            <p className="text-3xl font-black text-white">5</p>
            <p className="text-xs mt-0.5" style={{ color: '#8b949e' }}>Clases Hoy</p>
            <p className="text-xs mt-0.5 text-[#3b82f6]">2 en curso</p>
          </div>
        </div>

        <div className="rounded-xl p-5 flex items-center gap-4" style={CARD_STYLE}>
          <div className="w-10 h-10 rounded-full flex items-center justify-center shrink-0" style={{ backgroundColor: 'rgba(168,85,247,0.1)' }}>
            <svg className="w-5 h-5 text-[#a855f7]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
            </svg>
          </div>
          <div>
            <p className="text-3xl font-black text-white">{accesos?.accesos_hoy ?? 187}</p>
            <p className="text-xs mt-0.5" style={{ color: '#8b949e' }}>Asistencias</p>
            <p className="text-xs mt-0.5 text-[#a855f7]">hasta ahora</p>
          </div>
        </div>
      </div>

      {/* Resumen financiero badge */}
      <div className="rounded-xl p-4 flex items-center justify-between flex-wrap gap-2" style={CARD_STYLE}>
        <div className="flex items-center gap-2">
          <svg className="w-4 h-4 text-[#22c55e]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
          </svg>
          <span className="text-sm font-bold text-white">Resumen Financiero</span>
          <span className="text-[10px] px-2 py-0.5 rounded font-semibold" style={{ backgroundColor: '#f9731620', color: '#f97316' }}>Restringido</span>
        </div>
        <button className="text-xs flex items-center gap-1" style={{ color: '#8b949e' }}>
          Ver datos
          <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" /><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" /></svg>
        </button>
      </div>

      {/* Charts row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Afluencia */}
        <div className="lg:col-span-2 rounded-xl p-5" style={CARD_STYLE}>
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <svg className="w-4 h-4 text-[#22c55e]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <div>
                <p className="text-sm font-bold text-white">Afluencia por Hora</p>
                <p className="text-[10px]" style={{ color: '#8b949e' }}>Promedio de visitantes · Hoy</p>
              </div>
            </div>
            <span className="text-xs text-[#22c55e] flex items-center gap-1">
              <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 10l7-7m0 0l7 7m-7-7v18" /></svg>
              Pico: 6-7pm
            </span>
          </div>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={HORAS_MOCK} barSize={14}>
              <XAxis dataKey="hora" tick={{ fontSize: 10, fill: '#8b949e' }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fontSize: 10, fill: '#8b949e' }} axisLine={false} tickLine={false} />
              <Tooltip content={<CustomTooltip />} />
              <Bar dataKey="v" radius={[3, 3, 0, 0]}>
                {HORAS_MOCK.map((entry, i) => (
                  <Cell key={i} fill={entry.v >= 85 ? '#22c55e' : entry.v >= 50 ? '#16a34a' : '#166534'} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
          <div className="flex gap-4 mt-2">
            {[['Alta (+85)', '#22c55e'], ['Media (50-84)', '#16a34a'], ['Baja (-50)', '#166534']].map(([l, c]) => (
              <div key={l} className="flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full" style={{ backgroundColor: c }} />
                <span className="text-[10px]" style={{ color: '#8b949e' }}>{l}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Pagos pendientes */}
        <div className="rounded-xl p-5" style={CARD_STYLE}>
          <div className="flex items-center justify-between mb-4">
            <div>
              <p className="text-sm font-bold text-white">Pagos Pendientes</p>
              <p className="text-[10px]" style={{ color: '#8b949e' }}>Vencen hoy</p>
            </div>
            <span className="text-[10px] px-2 py-0.5 rounded font-bold" style={{ backgroundColor: '#f9731620', color: '#f97316' }}>3 hoy</span>
          </div>
          <div className="space-y-3">
            {PAGOS_MOCK.map(p => (
              <div key={p.id} className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <div className="w-8 h-8 rounded-full flex items-center justify-center text-[10px] font-bold shrink-0"
                    style={{ backgroundColor: avatarColor(p.nombre), color: '#0d1117' }}>
                    {initials(p.nombre)}
                  </div>
                  <div>
                    <p className="text-xs font-semibold text-white">{p.nombre}</p>
                    <p className="text-[10px]" style={{ color: '#8b949e' }}>{p.plan}</p>
                  </div>
                </div>
                <span className="text-xs font-bold" style={{ color: '#f97316' }}>${p.monto.toLocaleString()}</span>
              </div>
            ))}
          </div>
          <div className="mt-4 pt-3" style={{ borderTop: '1px solid #21262d' }}>
            <p className="text-xs" style={{ color: '#8b949e' }}>
              Total hoy: <span className="font-bold" style={{ color: '#22c55e' }}>$1,497</span>
            </p>
          </div>
        </div>
      </div>

      {/* Clases de hoy */}
      <div className="rounded-xl p-5" style={CARD_STYLE}>
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <svg className="w-4 h-4 text-[#3b82f6]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
            </svg>
            <p className="text-sm font-bold text-white">Clases de Hoy</p>
          </div>
          <span className="text-xs" style={{ color: '#3b82f6' }}>
            {new Date().toLocaleDateString('es-MX', { weekday: 'short', day: 'numeric', month: 'short' }).replace(/^\w/, c => c.toUpperCase())}
          </span>
        </div>
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          {CLASES_HOY_MOCK.map((c, i) => {
            const pct = Math.round((c.ocupacion / c.cupo) * 100)
            const barColor = pct >= 100 ? '#ef4444' : pct >= 80 ? '#22c55e' : '#3b82f6'
            return (
              <div key={i} className="rounded-lg p-4" style={{ backgroundColor: '#0d1117', border: '1px solid #21262d' }}>
                <div className="flex items-start justify-between mb-2">
                  <p className="text-xs font-bold text-white leading-tight">{c.nombre}</p>
                  <span className="text-[9px] px-1.5 py-0.5 rounded font-semibold ml-1 shrink-0"
                    style={{ backgroundColor: ESTADO_COLORS[c.estado] + '20', color: ESTADO_COLORS[c.estado] }}>
                    {c.estado}
                  </span>
                </div>
                <p className="text-[10px] mb-1" style={{ color: '#8b949e' }}>{c.hora}</p>
                <p className="text-[10px] mb-3" style={{ color: '#8b949e' }}>{c.profesor}</p>
                <div className="w-full h-1 rounded-full mb-1" style={{ backgroundColor: '#21262d' }}>
                  <div className="h-1 rounded-full transition-all" style={{ width: `${Math.min(pct, 100)}%`, backgroundColor: barColor }} />
                </div>
                <p className="text-[10px]" style={{ color: '#8b949e' }}>
                  Ocupación <span className="text-white font-semibold">{c.ocupacion}/{c.cupo}</span>
                </p>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}
