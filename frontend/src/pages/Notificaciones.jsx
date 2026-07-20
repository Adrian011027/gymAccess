import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import api from '../api/axios'

const CARD_STYLE = { backgroundColor: '#161b22', border: '1px solid #21262d' }

const TIPO_ICONO = {
  pago_vencido: { icon: '⚠', color: '#ef4444', label: 'Pago vencido' },
  inventario: { icon: '📦', color: '#3b82f6', label: 'Inventario' },
  membresia_por_vencer: { icon: '⏳', color: '#f97316', label: 'Membresía por vencer' },
  socio_nuevo: { icon: '👤', color: '#22c55e', label: 'Socio nuevo' },
  otro: { icon: '🔔', color: '#8b949e', label: 'General' },
}

function fechaCompleta(fecha) {
  return new Date(fecha).toLocaleString('es-MX', {
    day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit',
  })
}

export default function Notificaciones() {
  const navigate = useNavigate()
  const [notis, setNotis] = useState([])
  const [filtro, setFiltro] = useState('todos')

  useEffect(() => {
    api.get('/notificaciones/historial/').then(r => setNotis(r.data)).catch(() => {})
  }, [])

  const filtered = notis.filter(n => filtro === 'todos' ? true : n.tipo === filtro)

  const tipos = [...new Set(notis.map(n => n.tipo))]

  return (
    <div className="space-y-5">
      <div>
        <h2 className="text-xl font-black text-white uppercase tracking-wide">NOTIFICACIONES</h2>
        <p className="text-xs mt-0.5" style={{ color: '#8b949e' }}>Historial de los últimos 15 días</p>
      </div>

      <div className="flex gap-1 flex-wrap">
        {['todos', ...tipos].map(t => (
          <button
            key={t}
            onClick={() => setFiltro(t)}
            className="px-4 py-2 rounded-lg text-xs font-semibold transition-all"
            style={filtro === t
              ? { backgroundColor: '#22c55e', color: '#0d1117' }
              : { backgroundColor: '#161b22', color: '#8b949e', border: '1px solid #21262d' }
            }
          >{t === 'todos' ? 'Todos' : TIPO_ICONO[t]?.label || t}</button>
        ))}
      </div>

      <div className="rounded-xl overflow-hidden" style={CARD_STYLE}>
        {filtered.length === 0 && (
          <p className="text-xs text-center py-10" style={{ color: '#3d444d' }}>Sin notificaciones en este período</p>
        )}
        {filtered.map((n, i) => {
          const cfg = TIPO_ICONO[n.tipo] || TIPO_ICONO.otro
          return (
            <button
              key={n.id}
              onClick={() => n.link && navigate(n.link)}
              className="w-full flex items-start gap-3 px-5 py-4 text-left hover:bg-white/5 transition-colors"
              style={{ borderBottom: i < filtered.length - 1 ? '1px solid #21262d' : undefined }}
            >
              <span className="text-base shrink-0" style={{ color: cfg.color }}>{cfg.icon}</span>
              <div className="min-w-0 flex-1">
                <p className="text-sm" style={{ color: '#fff' }}>{n.mensaje}</p>
                <p className="text-[10px] mt-1" style={{ color: '#8b949e' }}>{cfg.label} · {fechaCompleta(n.creado_en)}</p>
              </div>
              {n.archivada && (
                <span className="text-[9px] px-2 py-0.5 rounded shrink-0" style={{ backgroundColor: 'rgba(139,148,158,0.15)', color: '#8b949e' }}>
                  Limpiada
                </span>
              )}
            </button>
          )
        })}
      </div>
    </div>
  )
}
