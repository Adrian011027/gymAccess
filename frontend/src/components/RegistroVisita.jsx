import { useEffect, useState } from 'react'
import api from '../api/axios'
import toast from 'react-hot-toast'

const CARD_STYLE = { backgroundColor: '#161b22', border: '1px solid #21262d' }
const INPUT_STYLE = { backgroundColor: '#0d1117', border: '1px solid #21262d', color: '#fff' }
const inputCls = 'w-full rounded-lg px-3 py-2 text-sm mt-1 outline-none text-white placeholder:text-[#3d444d]'

const METODOS = [['efectivo', 'Efectivo'], ['tarjeta', 'Tarjeta'], ['transferencia', 'Transferencia']]

const money = n => `$${Number(n || 0).toLocaleString('es-MX', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`

const VACIO = { nombre: '', apellido: '', telefono: '', metodo: 'efectivo', monto: '' }

/**
 * Alta del visitante de mostrador: cobra el día y le registra la entrada.
 *
 * Hasta ahora el que llegaba de la calle se cobraba a mano y se le abría la puerta,
 * así que su dinero no salía en el corte del día y su entrada no salía en la
 * afluencia. El backend lo resuelve en una sola operación (`/accesos/visita/`):
 * socio marcado como visita, membresía de un día, cobro y acceso.
 *
 * Quien ya vino antes se busca y se le cobra sobre su misma ficha: registrarlo otra
 * vez duplicaba a la persona en cada visita.
 */
export default function RegistroVisita({ sucursal, onRegistrada }) {
  const [abierto, setAbierto] = useState(false)
  const [planes, setPlanes] = useState([])
  const [plan, setPlan] = useState('')
  const [form, setForm] = useState(VACIO)
  const [guardando, setGuardando] = useState(false)
  const [busqueda, setBusqueda] = useState('')
  const [resultados, setResultados] = useState([])
  const [existente, setExistente] = useState(null)

  useEffect(() => {
    api.get('/socios/planes/')
      .then(r => {
        const visitas = r.data.filter(p => p.tipo === 'visita')
        setPlanes(visitas)
        if (visitas.length) setPlan(String(visitas[0].id))
      })
      .catch(() => {})
  }, [])

  // Busca mientras se escribe, con una pausa corta para no pedir por cada tecla.
  useEffect(() => {
    const termino = busqueda.trim()
    if (termino.length < 2) {
      setResultados([])
      return
    }
    const t = setTimeout(() => {
      api.get('/accesos/buscar-socio/', { params: { q: termino } })
        .then(r => setResultados(r.data))
        .catch(() => setResultados([]))
    }, 300)
    return () => clearTimeout(t)
  }, [busqueda])

  // El precio puede traer excepción por sucursal (`PrecioPlanSucursal`) y el backend
  // cobra esa. El botón tiene que decir lo mismo: anunciando el precio base, recepción
  // canta una cifra en la sucursal con descuento y el corte cierra con otra.
  const precioEn = p => {
    if (!p) return undefined
    const excepcion = (p.precios_sucursal || [])
      .find(x => String(x.sucursal) === String(sucursal))
    return excepcion ? excepcion.precio : p.precio
  }

  const planActual = planes.find(p => String(p.id) === String(plan))
  // El precio del plan es la referencia; el campo permite cortesías y promociones.
  const aCobrar = form.monto !== '' ? form.monto : precioEn(planActual)

  const limpiar = () => {
    setForm(VACIO)
    setExistente(null)
    setBusqueda('')
    setResultados([])
  }

  const registrar = async e => {
    e.preventDefault()
    if (!sucursal) return toast.error('Selecciona la sucursal')
    setGuardando(true)
    try {
      const persona = existente
        ? { socio: existente.id }
        : { nombre: form.nombre, apellido: form.apellido, telefono: form.telefono }
      const { data } = await api.post('/accesos/visita/', {
        ...persona,
        plan: Number(plan),
        sucursal: Number(sucursal),
        metodo: form.metodo,
        ...(form.monto !== '' ? { monto: form.monto } : {}),
      })
      toast.success(`${data.nombre} registrado · ${money(data.monto)} cobrado`)
      limpiar()
      setAbierto(false)
      onRegistrada?.(data)
    } catch (err) {
      const d = err?.response?.data
      toast.error(
        d?.socio?.[0] || d?.plan?.[0] || d?.sucursal?.[0] || d?.nombre?.[0] || d?.detail
        || 'No se pudo registrar la visita',
      )
    } finally {
      setGuardando(false)
    }
  }

  return (
    <div className="rounded-2xl p-4 sm:p-5" style={CARD_STYLE}>
      <div>
        <p className="text-[10px] font-bold tracking-widest" style={{ color: '#8b949e' }}>
          ¿NO ES SOCIO? REGISTRA SU VISITA
        </p>
        <p className="text-[10px] mt-1" style={{ color: '#3d444d' }}>
          Cobra el día, le abre la puerta y queda en el corte y en la afluencia.
        </p>
        <button
          onClick={() => setAbierto(a => !a)}
          className="w-full mt-3 px-4 py-2 rounded-lg text-xs font-bold"
          style={abierto
            ? { backgroundColor: '#21262d', color: '#8b949e' }
            : { backgroundColor: '#22c55e', color: '#0d1117' }}
        >
          {abierto ? 'Cerrar' : '+ Visita'}
        </button>
      </div>

      {abierto && (
        planes.length === 0 ? (
          // Sin plan de visita no hay precio que cobrar; se dice dónde se crea en vez
          // de dejar un formulario que va a fallar al enviarse.
          <div className="rounded-xl p-4 mt-4" style={{ backgroundColor: 'rgba(249,115,22,0.08)', border: '1px solid rgba(249,115,22,0.3)' }}>
            <p className="text-xs font-bold" style={{ color: '#f97316' }}>
              No hay ningún plan de tipo &quot;Visita Suelta&quot;
            </p>
            <p className="text-[10px] mt-1 leading-relaxed" style={{ color: '#8b949e' }}>
              Créalo en Configuración → Planes, con el precio del día. Sin él no se
              puede cobrar la visita.
            </p>
          </div>
        ) : (
          <form onSubmit={registrar} className="mt-4 space-y-3">
            {existente ? (
              <div className="rounded-lg p-3 flex items-center justify-between gap-2"
                style={{ backgroundColor: 'rgba(34,197,94,0.08)', border: '1px solid rgba(34,197,94,0.3)' }}>
                <div className="min-w-0">
                  <p className="text-xs font-bold text-white truncate">{existente.nombre}</p>
                  <p className="text-[10px]" style={{ color: '#8b949e' }}>
                    Ya está registrado{existente.numero_socio ? ` · #${existente.numero_socio}` : ''}: solo se cobra.
                  </p>
                </div>
                <button type="button" onClick={() => setExistente(null)}
                  className="text-[10px] font-semibold shrink-0" style={{ color: '#8b949e' }}>
                  Cambiar
                </button>
              </div>
            ) : (
              <>
                <label className="block">
                  <span className="text-[10px] tracking-widest" style={{ color: '#8b949e' }}>
                    ¿YA VINO ANTES? BÚSCALO
                  </span>
                  <input value={busqueda} onChange={e => setBusqueda(e.target.value)}
                    className={inputCls} style={INPUT_STYLE} placeholder="Nombre o número" />
                </label>
                {resultados.length > 0 && (
                  <div className="rounded-lg overflow-hidden" style={{ border: '1px solid #21262d' }}>
                    {resultados.map(r => (
                      <button key={r.id} type="button" disabled={r.al_corriente}
                        onClick={() => { setExistente(r); setResultados([]) }}
                        className="w-full text-left px-3 py-2 text-xs disabled:opacity-50"
                        style={{ backgroundColor: '#0d1117', borderBottom: '1px solid #21262d' }}>
                        <span className="text-white font-semibold">{r.nombre}</span>
                        <span className="block text-[10px]" style={{ color: r.al_corriente ? '#22c55e' : '#8b949e' }}>
                          {r.al_corriente
                            ? `Tiene ${r.plan} activo: regístralo en el check-in`
                            : `#${r.numero_socio ?? '—'} · sin membresía activa`}
                        </span>
                      </button>
                    ))}
                  </div>
                )}

                <p className="text-[10px] pt-1" style={{ color: '#3d444d' }}>O regístralo si es su primera vez:</p>
                <label className="block">
                  <span className="text-[10px] tracking-widest" style={{ color: '#8b949e' }}>NOMBRE</span>
                  <input value={form.nombre}
                    onChange={e => setForm(f => ({ ...f, nombre: e.target.value }))}
                    className={inputCls} style={INPUT_STYLE} placeholder="Nombre" />
                </label>
                <label className="block">
                  <span className="text-[10px] tracking-widest" style={{ color: '#8b949e' }}>APELLIDO</span>
                  <input value={form.apellido}
                    onChange={e => setForm(f => ({ ...f, apellido: e.target.value }))}
                    className={inputCls} style={INPUT_STYLE} placeholder="Opcional" />
                </label>
                <label className="block">
                  <span className="text-[10px] tracking-widest" style={{ color: '#8b949e' }}>TELÉFONO</span>
                  <input value={form.telefono}
                    onChange={e => setForm(f => ({ ...f, telefono: e.target.value }))}
                    className={inputCls} style={INPUT_STYLE} placeholder="Opcional" />
                </label>
              </>
            )}

            <label className="block">
              <span className="text-[10px] tracking-widest" style={{ color: '#8b949e' }}>PLAN</span>
              <select value={plan} onChange={e => setPlan(e.target.value)}
                className={inputCls} style={INPUT_STYLE}>
                {planes.map(p => (
                  <option key={p.id} value={p.id}>{p.nombre} · {money(precioEn(p))}</option>
                ))}
              </select>
            </label>

            <div>
              <span className="text-[10px] tracking-widest" style={{ color: '#8b949e' }}>MÉTODO DE PAGO</span>
              <div className="grid grid-cols-3 gap-2 mt-1">
                {METODOS.map(([v, l]) => (
                  <button key={v} type="button"
                    onClick={() => setForm(f => ({ ...f, metodo: v }))}
                    className="py-2 rounded-lg text-[11px] font-semibold transition-all"
                    style={form.metodo === v
                      ? { backgroundColor: '#22c55e', color: '#0d1117' }
                      : { backgroundColor: '#0d1117', color: '#8b949e', border: '1px solid #21262d' }}
                  >{l}</button>
                ))}
              </div>
            </div>

            <label className="block">
              <span className="text-[10px] tracking-widest" style={{ color: '#8b949e' }}>
                MONTO — deja vacío para cobrar el precio del plan
              </span>
              <input type="number" step="0.01" min="0" value={form.monto}
                onChange={e => setForm(f => ({ ...f, monto: e.target.value }))}
                className={inputCls} style={INPUT_STYLE}
                placeholder={planActual ? String(precioEn(planActual)) : ''} />
            </label>

            <button type="submit" disabled={guardando || (!existente && !form.nombre.trim())}
              className="w-full py-2.5 rounded-lg text-xs font-bold transition-all disabled:opacity-40"
              style={{ backgroundColor: '#22c55e', color: '#0d1117' }}>
              {guardando ? 'Registrando...' : `Cobrar ${money(aCobrar)} y registrar entrada`}
            </button>
          </form>
        )
      )}
    </div>
  )
}
