import { useEffect, useState } from 'react'
import { XAxis, YAxis, Tooltip, ResponsiveContainer, Area, AreaChart } from 'recharts'
import api from '../api/axios'

const CARD_STYLE = { backgroundColor: '#161b22', border: '1px solid #21262d' }
const CAT_COLOR = {
  renta: '#f97316', nomina: '#ef4444', equipo: '#3b82f6',
  servicios: '#eab308', mantenimiento: '#a855f7', marketing: '#06b6d4', otro: '#8b949e',
}
const CAT_LABEL = {
  renta: 'Renta', nomina: 'Nómina', equipo: 'Equipo',
  servicios: 'Servicios', mantenimiento: 'Mantenimiento', marketing: 'Marketing', otro: 'Otro',
}
const MESES = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic']

function fmt(n) {
  if (n >= 1000) return `$${(n / 1000).toFixed(0)}k`
  return `$${n}`
}

function mesKey(fechaISO) {
  const d = new Date(fechaISO)
  return `${d.getFullYear()}-${d.getMonth()}`
}

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null
  return (
    <div className="px-3 py-2 rounded-lg text-xs" style={{ backgroundColor: '#1c2333', border: '1px solid #21262d', color: '#fff' }}>
      <p style={{ color: '#8b949e' }}>{label}</p>
      <p className="font-bold text-[#22c55e]">Ingresos: ${payload[0]?.value?.toLocaleString()}</p>
      {payload[1] && <p className="font-bold text-[#f97316]">Gastos: ${payload[1].value.toLocaleString()}</p>}
    </div>
  )
}

export default function Reportes() {
  const [pagos, setPagos] = useState([])
  const [gastos, setGastos] = useState([])

  useEffect(() => {
    api.get('/socios/pagos/').then(r => setPagos(r.data)).catch(() => {})
    api.get('/socios/gastos/').then(r => setGastos(r.data)).catch(() => {})
  }, [])

  const hoy = new Date()
  const inicioMes = new Date(hoy.getFullYear(), hoy.getMonth(), 1)
  const inicioMesAnt = new Date(hoy.getFullYear(), hoy.getMonth() - 1, 1)

  const pagosMes = pagos.filter(p => new Date(p.fecha) >= inicioMes)
  const pagosMesAnt = pagos.filter(p => new Date(p.fecha) >= inicioMesAnt && new Date(p.fecha) < inicioMes)
  const gastosMes = gastos.filter(g => new Date(g.fecha) >= inicioMes)
  const gastosMesAnt = gastos.filter(g => new Date(g.fecha) >= inicioMesAnt && new Date(g.fecha) < inicioMes)

  const ingresos = pagosMes.reduce((s, p) => s + Number(p.monto || 0), 0)
  const ingresosAnt = pagosMesAnt.reduce((s, p) => s + Number(p.monto || 0), 0)
  const gastosTotal = gastosMes.reduce((s, g) => s + Number(g.monto || 0), 0)
  const gastosTotalAnt = gastosMesAnt.reduce((s, g) => s + Number(g.monto || 0), 0)
  const ganancia = ingresos - gastosTotal

  const variacion = (actual, anterior) => {
    if (!anterior) return null
    return ((actual - anterior) / anterior) * 100
  }
  const varIngresos = variacion(ingresos, ingresosAnt)
  const varGastos = variacion(gastosTotal, gastosTotalAnt)

  // Serie de los últimos 7 meses: ingresos vs gastos
  const serie = []
  for (let i = 6; i >= 0; i--) {
    const d = new Date(hoy.getFullYear(), hoy.getMonth() - i, 1)
    const key = `${d.getFullYear()}-${d.getMonth()}`
    serie.push({
      mes: MESES[d.getMonth()],
      ingresos: pagos.filter(p => mesKey(p.fecha) === key).reduce((s, p) => s + Number(p.monto || 0), 0),
      gastos: gastos.filter(g => mesKey(g.fecha) === key).reduce((s, g) => s + Number(g.monto || 0), 0),
    })
  }

  // Desglose de gastos por categoría (mes en curso)
  const porCategoria = {}
  for (const g of gastosMes) {
    porCategoria[g.categoria] = (porCategoria[g.categoria] || 0) + Number(g.monto || 0)
  }
  const desgloseGastos = Object.entries(porCategoria)
    .map(([cat, monto]) => ({ cat, monto, pct: gastosTotal ? Math.round((monto / gastosTotal) * 100) : 0 }))
    .sort((a, b) => b.monto - a.monto)

  // Ingresos por plan (mes en curso)
  const porPlan = {}
  for (const p of pagosMes) {
    const key = p.plan_nombre || 'Sin plan'
    if (!porPlan[key]) porPlan[key] = { monto: 0, count: 0 }
    porPlan[key].monto += Number(p.monto || 0)
    porPlan[key].count += 1
  }
  const ingresosPorPlan = Object.entries(porPlan).sort((a, b) => b[1].monto - a[1].monto)

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-xl font-black text-white uppercase tracking-wide">REPORTES</h2>
          <p className="text-xs mt-0.5" style={{ color: '#8b949e' }}>
            Período: {hoy.toLocaleDateString('es-MX', { month: 'long', year: 'numeric' }).replace(/^\w/, c => c.toUpperCase())}
          </p>
        </div>
      </div>

      {/* KPI cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="rounded-xl p-5" style={CARD_STYLE}>
          <div className="flex items-center justify-between mb-2">
            <p className="text-xs font-semibold" style={{ color: '#8b949e' }}>Ingresos Totales</p>
            <svg className="w-4 h-4 text-[#22c55e]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
            </svg>
          </div>
          <p className="text-2xl font-black text-white">${ingresos.toLocaleString()}</p>
          <p className="text-[10px] mt-1" style={{ color: varIngresos == null ? '#3d444d' : varIngresos >= 0 ? '#22c55e' : '#ef4444' }}>
            {varIngresos == null ? 'Sin datos del mes anterior' : `${varIngresos >= 0 ? '+' : ''}${varIngresos.toFixed(1)}% vs. mes ant.`}
          </p>
        </div>
        <div className="rounded-xl p-5" style={CARD_STYLE}>
          <div className="flex items-center justify-between mb-2">
            <p className="text-xs font-semibold" style={{ color: '#8b949e' }}>Gastos Totales</p>
            <svg className="w-4 h-4 text-[#f97316]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
            </svg>
          </div>
          <p className="text-2xl font-black text-white">${gastosTotal.toLocaleString()}</p>
          <p className="text-[10px] mt-1" style={{ color: varGastos == null ? '#3d444d' : varGastos <= 0 ? '#22c55e' : '#f97316' }}>
            {varGastos == null ? 'Sin datos del mes anterior' : `${varGastos >= 0 ? '+' : ''}${varGastos.toFixed(1)}% vs. mes ant.`}
          </p>
        </div>
        <div className="rounded-xl p-5" style={CARD_STYLE}>
          <div className="flex items-center justify-between mb-2">
            <p className="text-xs font-semibold" style={{ color: '#8b949e' }}>Ganancia Neta</p>
            <svg className="w-4 h-4 text-[#3b82f6]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
            </svg>
          </div>
          <p className="text-2xl font-black text-white">${ganancia.toLocaleString()}</p>
          <p className="text-[10px] mt-1" style={{ color: '#3b82f6' }}>
            Margen: {ingresos > 0 ? Math.round((ganancia / ingresos) * 100) : 0}%
          </p>
        </div>
      </div>

      {/* Chart */}
      <div className="rounded-xl p-5" style={CARD_STYLE}>
        <div className="flex items-center gap-2 mb-5">
          <svg className="w-4 h-4 text-[#22c55e]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
          </svg>
          <div>
            <p className="text-sm font-bold text-white">Ingresos vs. Gastos</p>
            <p className="text-[10px]" style={{ color: '#8b949e' }}>Últimos 7 meses</p>
          </div>
        </div>
        <ResponsiveContainer width="100%" height={220}>
          <AreaChart data={serie}>
            <defs>
              <linearGradient id="colorIngresos" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#22c55e" stopOpacity={0.15} />
                <stop offset="95%" stopColor="#22c55e" stopOpacity={0} />
              </linearGradient>
              <linearGradient id="colorGastos" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#f97316" stopOpacity={0.12} />
                <stop offset="95%" stopColor="#f97316" stopOpacity={0} />
              </linearGradient>
            </defs>
            <XAxis dataKey="mes" tick={{ fontSize: 11, fill: '#8b949e' }} axisLine={false} tickLine={false} />
            <YAxis tick={{ fontSize: 11, fill: '#8b949e' }} axisLine={false} tickLine={false} tickFormatter={fmt} />
            <Tooltip content={<CustomTooltip />} />
            <Area type="monotone" dataKey="ingresos" stroke="#22c55e" strokeWidth={2} fill="url(#colorIngresos)" dot={false} />
            <Area type="monotone" dataKey="gastos" stroke="#f97316" strokeWidth={2} fill="url(#colorGastos)" dot={false} />
          </AreaChart>
        </ResponsiveContainer>
      </div>

      {/* Desglose */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Desglose de gastos */}
        <div className="rounded-xl p-5" style={CARD_STYLE}>
          <div className="flex items-center gap-2 mb-4">
            <div className="w-3 h-3 rounded-sm" style={{ backgroundColor: '#f97316' }} />
            <div>
              <p className="text-sm font-bold text-white">Desglose de Gastos</p>
              <p className="text-[10px]" style={{ color: '#8b949e' }}>
                {hoy.toLocaleDateString('es-MX', { month: 'long', year: 'numeric' }).replace(/^\w/, c => c.toUpperCase())}
              </p>
            </div>
          </div>
          <div className="space-y-3">
            {desgloseGastos.map(g => (
              <div key={g.cat}>
                <div className="flex justify-between mb-1">
                  <span className="text-xs" style={{ color: '#8b949e' }}>{CAT_LABEL[g.cat] || g.cat}</span>
                  <span className="text-xs font-bold text-white">${g.monto.toLocaleString()} <span style={{ color: '#8b949e' }}>{g.pct}%</span></span>
                </div>
                <div className="w-full h-1 rounded-full" style={{ backgroundColor: '#21262d' }}>
                  <div className="h-1 rounded-full" style={{ width: `${g.pct}%`, backgroundColor: CAT_COLOR[g.cat] || '#8b949e' }} />
                </div>
              </div>
            ))}
            {desgloseGastos.length === 0 && (
              <p className="text-xs text-center py-4" style={{ color: '#3d444d' }}>Sin gastos este mes</p>
            )}
          </div>
        </div>

        {/* Ingresos por plan */}
        <div className="rounded-xl p-5" style={CARD_STYLE}>
          <div className="flex items-center gap-2 mb-4">
            <div className="w-3 h-3 rounded-sm" style={{ backgroundColor: '#22c55e' }} />
            <div>
              <p className="text-sm font-bold text-white">Ingresos por Plan</p>
              <p className="text-[10px]" style={{ color: '#8b949e' }}>
                {hoy.toLocaleDateString('es-MX', { month: 'long', year: 'numeric' }).replace(/^\w/, c => c.toUpperCase())}
              </p>
            </div>
          </div>
          <div className="space-y-4">
            {ingresosPorPlan.map(([nombre, d]) => (
              <div key={nombre} className="flex justify-between items-center">
                <div>
                  <p className="text-sm font-bold text-white">{nombre}</p>
                  <p className="text-[10px]" style={{ color: '#8b949e' }}>{d.count} pago{d.count !== 1 ? 's' : ''}</p>
                </div>
                <span className="text-sm font-black" style={{ color: '#22c55e' }}>${d.monto.toLocaleString()}</span>
              </div>
            ))}
            {ingresosPorPlan.length === 0 && (
              <p className="text-xs text-center py-4" style={{ color: '#3d444d' }}>Sin pagos este mes</p>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
