import { useEffect, useState } from 'react'
import api from '../api/axios'
import { useAuth } from '../context/AuthContext'

const INPUT_STYLE = { backgroundColor: '#0d1117', border: '1px solid #21262d', color: '#fff' }

/**
 * Selector "Todas / <sucursal>" para el dueño.
 *
 * A quien está atado a una sucursal no se le muestra nada: no tiene nada que elegir,
 * y el backend le ignora el parámetro de todos modos.
 *
 * Llama a `onChange(query)` con el sufijo listo para pegar a la URL ('' o '?sucursal=N').
 */
export default function SucursalSelector({ onChange }) {
  const { verTodasLasSucursales } = useAuth()
  const [sucursales, setSucursales] = useState([])
  const [valor, setValor] = useState('')

  useEffect(() => {
    if (!verTodasLasSucursales) return
    api.get('/gyms/sucursales/').then(r => setSucursales(r.data)).catch(() => {})
  }, [verTodasLasSucursales])

  const cambiar = v => {
    setValor(v)
    onChange(v ? `?sucursal=${v}` : '')
  }

  // Con una sola sucursal el selector solo estorba.
  if (!verTodasLasSucursales || sucursales.length < 2) return null

  return (
    <select
      value={valor}
      onChange={e => cambiar(e.target.value)}
      className="rounded-lg px-3 py-2 text-xs font-semibold"
      style={INPUT_STYLE}
    >
      <option value="">Todas las sucursales</option>
      {sucursales.map(s => <option key={s.id} value={s.id}>{s.nombre}</option>)}
    </select>
  )
}
