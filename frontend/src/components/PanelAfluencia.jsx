import { useEffect, useState } from 'react'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts'
import api from '../api/axios'

const CARD_STYLE = { backgroundColor: '#161b22', border: '1px solid #21262d' }
const INPUT_STYLE = { backgroundColor: '#0d1117', border: '1px solid #21262d', color: '#fff' }

// Etiqueta de hora legible para el eje del gráfico y el "pico". `hora_pico` del
// backend es un entero 0-23; se traduce aquí en vez de mandarlo ya formateado
// porque el mismo número también hace falta crudo para ordenar y comparar.
export function horaLabel(h) {
  if (h === 0) return '12am'
  if (h === 12) return '12pm'
  return h < 12 ? `${h}am` : `${h - 12}pm`
}

/**
 * Afluencia por hora y visitas del período.
 *
 * Sale del Dashboard a un componente propio porque el dato le sirve a todo el mundo
 * —recepción decide cuándo hacer el corte, el coach cuándo programar clase— pero el
 * Dashboard mezcla esto con ingresos y cobros pendientes, que sí son solo del dueño.
 * Duplicar el gráfico para abrirlo a los demás habría sido la otra opción, y es como
 * dos pantallas acaban contando visitas distintas.
 *
 * El backend (`StatsView`) ya acota por sucursal según quién pregunte: recepción ve
 * la suya, el dueño el gym completo o la que pida con `?sucursal=`.
 */
export default function PanelAfluencia({ sucursal = '' }) {
  const [datos, setDatos] = useState(null)
  const [rango, setRango] = useState('semana')

  useEffect(() => {
    const params = new URLSearchParams(sucursal.replace(/^\?/, ''))
    params.set('rango', rango)
    api.get(`/accesos/stats/?${params}`)
      .then(r => setDatos(r.data))
      .catch(() => setDatos(null))
  }, [sucursal, rango])

  const barras = (datos?.horarios_concurridos || []).map(h => ({
    hora: horaLabel(h.hora), v: h.promedio,
  }))
  const maximo = Math.max(0, ...barras.map(d => d.v))

  const Tip = ({ active, payload, label }) => {
    if (!active || !payload?.length) return null
    const v = payload[0].value
    const color = v >= maximo * 0.7 ? '#22c55e' : v >= maximo * 0.4 ? '#86efac' : '#4ade80'
    return (
      <div className="px-3 py-2 rounded-lg text-xs" style={{ backgroundColor: '#1c2333', border: '1px solid #21262d', color: '#fff' }}>
        <p className="font-bold">{label}</p>
        <p style={{ color }}>{v} visitantes{rango === 'semana' ? ' (promedio)' : ''}</p>
      </div>
    )
  }

  return (
    <div className="rounded-xl p-5" style={CARD_STYLE}>
      <div className="flex items-center justify-between mb-4 flex-wrap gap-2">
        <div className="flex items-center gap-2">
          <svg className="w-4 h-4 text-[#22c55e]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <div>
            <p className="text-sm font-bold text-white">Afluencia por Hora</p>
            <p className="text-[10px]" style={{ color: '#8b949e' }}>
              {rango === 'semana' ? 'Promedio de visitantes · últimos 7 días' : 'Visitantes · Hoy'}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {datos?.hora_pico != null && (
            <span className="text-xs text-[#22c55e] flex items-center gap-1">
              <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 10l7-7m0 0l7 7m-7-7v18" /></svg>
              Pico: {horaLabel(datos.hora_pico)}
            </span>
          )}
          <select
            value={rango}
            onChange={e => setRango(e.target.value)}
            className="text-xs px-2 py-1.5 rounded-lg font-semibold outline-none"
            style={INPUT_STYLE}
          >
            <option value="semana">Últimos 7 días</option>
            <option value="hoy">Hoy</option>
          </select>
        </div>
      </div>

      {barras.length === 0 ? (
        <div className="flex items-center justify-center" style={{ height: 200 }}>
          <p className="text-xs" style={{ color: '#3d444d' }}>
            {rango === 'semana' ? 'Sin accesos registrados en los últimos 7 días' : 'Sin accesos registrados hoy'}
          </p>
        </div>
      ) : (
        <>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={barras} barSize={14}>
              <XAxis dataKey="hora" tick={{ fontSize: 10, fill: '#8b949e' }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fontSize: 10, fill: '#8b949e' }} axisLine={false} tickLine={false} allowDecimals={false} />
              <Tooltip content={<Tip />} />
              <Bar dataKey="v" radius={[3, 3, 0, 0]}>
                {barras.map((entry, i) => (
                  <Cell key={i} fill={
                    entry.v >= maximo * 0.7 ? '#22c55e'
                      : entry.v >= maximo * 0.4 ? '#16a34a' : '#166534'
                  } />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
          <div className="flex gap-4 mt-2">
            {[['Alta', '#22c55e'], ['Media', '#16a34a'], ['Baja', '#166534']].map(([l, c]) => (
              <div key={l} className="flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full" style={{ backgroundColor: c }} />
                <span className="text-[10px]" style={{ color: '#8b949e' }}>{l}</span>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  )
}
