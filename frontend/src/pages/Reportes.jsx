import { useEffect, useState } from 'react'
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, Area, AreaChart } from 'recharts'
import api from '../api/axios'

const CARD_STYLE = { backgroundColor: '#161b22', border: '1px solid #21262d' }

const INGRESOS_MOCK = [
  { mes: 'Ene', ingresos: 220000 }, { mes: 'Feb', ingresos: 235000 }, { mes: 'Mar', ingresos: 248000 },
  { mes: 'Abr', ingresos: 255000 }, { mes: 'May', ingresos: 262000 }, { mes: 'Jun', ingresos: 274000 },
  { mes: 'Jul', ingresos: 284500 },
]

const GASTOS_CAT = [
  { label: 'Nómina / Staff', pct: 49, monto: 42000, color: '#f97316' },
  { label: 'Renta / Local', pct: 21, monto: 18000, color: '#f97316' },
  { label: 'Servicios (luz, agua)', pct: 10, monto: 8500, color: '#f97316' },
  { label: 'Mantenimiento Equipo', pct: 8, monto: 6800, color: '#f97316' },
]

function fmt(n) {
  if (n >= 1000) return `$${(n / 1000).toFixed(0)}k`
  return `$${n}`
}

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null
  return (
    <div className="px-3 py-2 rounded-lg text-xs" style={{ backgroundColor: '#1c2333', border: '1px solid #21262d', color: '#fff' }}>
      <p style={{ color: '#8b949e' }}>{label}</p>
      <p className="font-bold text-[#22c55e]">${payload[0].value.toLocaleString()}</p>
    </div>
  )
}

export default function Reportes() {
  const [socios, setSocios] = useState([])
  useEffect(() => {
    api.get('/socios/').then(r => setSocios(r.data)).catch(() => {})
  }, [])

  const activos = socios.filter(s => s.activo).length
  const ingresosEstimados = activos * 499
  const gastosEst = 75300
  const ganancia = ingresosEstimados - gastosEst

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-black text-white uppercase tracking-wide">REPORTES</h2>
          <p className="text-xs mt-0.5" style={{ color: '#8b949e' }}>
            Período: {new Date().toLocaleDateString('es-MX', { month: 'long', year: 'numeric' }).replace(/^\w/, c => c.toUpperCase())}
          </p>
        </div>
        <button
          className="flex items-center gap-2 text-xs font-semibold transition-colors hover:opacity-80"
          style={{ color: '#22c55e' }}
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
          </svg>
          Exportar PDF
        </button>
      </div>

      {/* KPI cards */}
      <div className="grid grid-cols-3 gap-4">
        <div className="rounded-xl p-5" style={CARD_STYLE}>
          <div className="flex items-center justify-between mb-2">
            <p className="text-xs font-semibold" style={{ color: '#8b949e' }}>Ingresos Totales</p>
            <svg className="w-4 h-4 text-[#22c55e]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
            </svg>
          </div>
          <p className="text-2xl font-black text-white">${ingresosEstimados.toLocaleString()}</p>
          <p className="text-[10px] mt-1 text-[#22c55e]">+12.4% vs. mes ant.</p>
        </div>
        <div className="rounded-xl p-5" style={CARD_STYLE}>
          <div className="flex items-center justify-between mb-2">
            <p className="text-xs font-semibold" style={{ color: '#8b949e' }}>Gastos Totales</p>
            <svg className="w-4 h-4 text-[#f97316]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
            </svg>
          </div>
          <p className="text-2xl font-black text-white">${gastosEst.toLocaleString()}</p>
          <p className="text-[10px] mt-1 text-[#f97316]">+3.1% vs. mes ant.</p>
        </div>
        <div className="rounded-xl p-5" style={CARD_STYLE}>
          <div className="flex items-center justify-between mb-2">
            <p className="text-xs font-semibold" style={{ color: '#8b949e' }}>Ganancia Neta</p>
            <svg className="w-4 h-4 text-[#3b82f6]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
            </svg>
          </div>
          <p className="text-2xl font-black text-white">${Math.max(0, ganancia).toLocaleString()}</p>
          <p className="text-[10px] mt-1 text-[#3b82f6]">
            Margen: {ingresosEstimados > 0 ? Math.round((ganancia / ingresosEstimados) * 100) : 0}%
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
          <AreaChart data={INGRESOS_MOCK}>
            <defs>
              <linearGradient id="colorIngresos" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#22c55e" stopOpacity={0.15} />
                <stop offset="95%" stopColor="#22c55e" stopOpacity={0} />
              </linearGradient>
            </defs>
            <XAxis dataKey="mes" tick={{ fontSize: 11, fill: '#8b949e' }} axisLine={false} tickLine={false} />
            <YAxis tick={{ fontSize: 11, fill: '#8b949e' }} axisLine={false} tickLine={false} tickFormatter={fmt} />
            <Tooltip content={<CustomTooltip />} />
            <Area type="monotone" dataKey="ingresos" stroke="#22c55e" strokeWidth={2} fill="url(#colorIngresos)" dot={false} />
          </AreaChart>
        </ResponsiveContainer>
      </div>

      {/* Desglose */}
      <div className="grid grid-cols-2 gap-4">
        {/* Desglose de gastos */}
        <div className="rounded-xl p-5" style={CARD_STYLE}>
          <div className="flex items-center gap-2 mb-4">
            <div className="w-3 h-3 rounded-sm" style={{ backgroundColor: '#f97316' }} />
            <div>
              <p className="text-sm font-bold text-white">Desglose de Gastos</p>
              <p className="text-[10px]" style={{ color: '#8b949e' }}>
                {new Date().toLocaleDateString('es-MX', { month: 'long', year: 'numeric' }).replace(/^\w/, c => c.toUpperCase())}
              </p>
            </div>
          </div>
          <div className="space-y-3">
            {GASTOS_CAT.map(g => (
              <div key={g.label}>
                <div className="flex justify-between mb-1">
                  <span className="text-xs" style={{ color: '#8b949e' }}>{g.label}</span>
                  <span className="text-xs font-bold text-white">${g.monto.toLocaleString()} <span style={{ color: '#8b949e' }}>{g.pct}%</span></span>
                </div>
                <div className="w-full h-1 rounded-full" style={{ backgroundColor: '#21262d' }}>
                  <div className="h-1 rounded-full" style={{ width: `${g.pct}%`, backgroundColor: g.color }} />
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Ingresos por plan */}
        <div className="rounded-xl p-5" style={CARD_STYLE}>
          <div className="flex items-center gap-2 mb-4">
            <div className="w-3 h-3 rounded-sm" style={{ backgroundColor: '#22c55e' }} />
            <div>
              <p className="text-sm font-bold text-white">Ingresos por Plan</p>
              <p className="text-[10px]" style={{ color: '#8b949e' }}>
                {new Date().toLocaleDateString('es-MX', { month: 'long', year: 'numeric' }).replace(/^\w/, c => c.toUpperCase())}
              </p>
            </div>
          </div>
          <div className="space-y-4">
            <div className="flex justify-between items-center">
              <div>
                <p className="text-sm font-bold text-white">Socio Regular</p>
                <p className="text-[10px]" style={{ color: '#8b949e' }}>{activos} socios × $499/mes</p>
              </div>
              <span className="text-sm font-black" style={{ color: '#22c55e' }}>${ingresosEstimados.toLocaleString()}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
