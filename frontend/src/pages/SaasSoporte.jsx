import { useEffect, useState } from 'react'
import api from '../api/axios'
import { T } from '../components/layout/saasTheme'

const panel = { backgroundColor: T.panel, border: `1px solid ${T.bordeSuave}` }

const fecha = iso => {
  const d = new Date(iso)
  return d.toLocaleString('es-MX', {
    day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit',
  })
}

export default function SaasSoporte() {
  const [registros, setRegistros] = useState([])
  const [cargando, setCargando] = useState(true)

  useEffect(() => {
    api.get('/saas/soporte/')
      .then(r => setRegistros(r.data))
      .catch(() => {})
      .finally(() => setCargando(false))
  }, [])

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-base font-bold">Bitácora de soporte</h1>
        <p className="text-[11px] mt-1 leading-relaxed" style={{ color: T.tenue }}>
          Cada vez que entraste como un cliente. Es la evidencia con la que se le
          responde a un gimnasio que pregunte quién vio los datos de sus socios.
        </p>
      </div>

      <div className="rounded-xl overflow-hidden" style={panel}>
        <div className="overflow-x-auto">
          <table className="w-full" style={{ minWidth: '720px' }}>
            <thead>
              <tr style={{ borderBottom: `1px solid ${T.bordeSuave}`, backgroundColor: T.panelAlto }}>
                {['Cuándo', 'Gimnasio', 'Quién entró', 'Como', 'Motivo', 'IP'].map(h => (
                  <th key={h} className="text-left text-[9px] font-bold tracking-[0.14em] px-4 py-2.5"
                    style={{ color: T.apagado }}>
                    {h.toUpperCase()}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {registros.map(r => (
                <tr key={r.id} style={{ borderBottom: `1px solid ${T.bordeSuave}` }}>
                  <td className="px-4 py-3 text-[11px] whitespace-nowrap" style={{ color: T.tenue }}>
                    {fecha(r.creado_en)}
                  </td>
                  <td className="px-4 py-3 text-[12px] font-bold">{r.gym_nombre}</td>
                  <td className="px-4 py-3 text-[11px]">{r.superadmin_nombre ?? '—'}</td>
                  <td className="px-4 py-3 text-[11px]" style={{ color: T.tenue }}>
                    {r.suplantado_nombre ?? '—'}
                  </td>
                  <td className="px-4 py-3 text-[11px]" style={{ color: T.texto }}>{r.motivo}</td>
                  <td className="px-4 py-3 text-[10px] tabular-nums" style={{ color: T.apagado }}>
                    {r.ip ?? '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {!cargando && registros.length === 0 && (
            <p className="text-[11px] text-center py-8" style={{ color: T.apagado }}>
              Todavía no has entrado como ningún cliente
            </p>
          )}
        </div>
      </div>
    </div>
  )
}
