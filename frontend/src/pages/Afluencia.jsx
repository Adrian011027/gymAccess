import { useEffect, useState } from 'react'
import api from '../api/axios'
import SucursalSelector from '../components/SucursalSelector'
import PanelAfluencia from '../components/PanelAfluencia'
import { useAuth } from '../context/AuthContext'

const CARD_STYLE = { backgroundColor: '#161b22', border: '1px solid #21262d' }

/**
 * Afluencia y visitas, abierta a todos los roles.
 *
 * El mismo gráfico vive en el Dashboard, pero ese está reservado al dueño porque
 * mezcla ingresos y cobros pendientes. Recepción y los coaches necesitan el dato de
 * afluencia sin ver nada de dinero: quién decide cuándo hacer el corte o a qué hora
 * programar una clase es justamente quien está en el piso.
 */
export default function Afluencia() {
  const { sucursalNombre, verTodasLasSucursales } = useAuth()
  const [q, setQ] = useState('')
  const [stats, setStats] = useState(null)

  useEffect(() => {
    const params = new URLSearchParams(q.replace(/^\?/, ''))
    params.set('rango', 'hoy')
    api.get(`/accesos/stats/?${params}`)
      .then(r => setStats(r.data))
      .catch(() => setStats(null))
  }, [q])

  const tarjetas = [
    ['Visitas hoy', stats?.accesos_hoy],
    ['Visitas del mes', stats?.accesos_mes],
    ['Hora pico', stats?.hora_pico != null ? `${stats.hora_pico}:00` : null],
  ]

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-xl font-black text-white uppercase tracking-wide">AFLUENCIA</h2>
          <p className="text-xs mt-0.5" style={{ color: '#8b949e' }}>
            {verTodasLasSucursales ? 'Todas las sucursales' : sucursalNombre || 'Tu sucursal'}
          </p>
        </div>
        <SucursalSelector onChange={setQ} />
      </div>

      <div className="grid gap-3 grid-cols-3">
        {tarjetas.map(([label, valor]) => (
          <div key={label} className="rounded-xl p-4" style={CARD_STYLE}>
            <p className="text-[10px] tracking-widest" style={{ color: '#8b949e' }}>{label.toUpperCase()}</p>
            <p className="text-lg font-black text-white mt-1">{valor ?? '—'}</p>
          </div>
        ))}
      </div>

      <PanelAfluencia sucursal={q} />
    </div>
  )
}
