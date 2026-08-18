import { useCallback, useEffect, useMemo, useState } from 'react'
import api from '../api/axios'
import toast from 'react-hot-toast'
import { useAuth } from '../context/AuthContext'

const CARD_STYLE = { backgroundColor: '#161b22', border: '1px solid #21262d' }
const INPUT_STYLE = { backgroundColor: '#0d1117', border: '1px solid #21262d', color: '#fff' }
const inputCls = 'w-full rounded-lg px-3 py-2 text-sm mt-1 focus:outline-none'

const CATEGORIAS = ['bebida', 'suplemento', 'snack', 'accesorio', 'otro']
const CAT_LABEL = {
  bebida: 'Bebidas', suplemento: 'Suplementos', snack: 'Snacks',
  accesorio: 'Accesorios', otro: 'Otro',
}
const METODOS = [
  { v: 'efectivo', label: 'Efectivo' },
  { v: 'tarjeta', label: 'Tarjeta' },
  { v: 'transferencia', label: 'Transferencia' },
]

const EMPTY_PRODUCTO = {
  nombre: '', categoria: 'bebida', precio: '', costo: '', stock_inicial: 0,
}

const money = n => `$${Number(n || 0).toLocaleString('es-MX', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`

export default function POS() {
  const { isAdmin, sucursalId, verTodasLasSucursales } = useAuth()
  const [tab, setTab] = useState('caja')
  const [productos, setProductos] = useState([])
  const [sucursales, setSucursales] = useState([])
  const [ventas, setVentas] = useState([])
  const [resumen, setResumen] = useState(null)

  const [carrito, setCarrito] = useState([])   // [{ id, nombre, precio, cantidad, stock }]
  const [metodo, setMetodo] = useState('efectivo')
  const [sucursal, setSucursal] = useState('')
  const [cobrando, setCobrando] = useState(false)
  const [busqueda, setBusqueda] = useState('')
  const [catFiltro, setCatFiltro] = useState('todos')

  const [modal, setModal] = useState(false)
  const [form, setForm] = useState(EMPTY_PRODUCTO)
  const [guardando, setGuardando] = useState(false)

  // Los errores se muestran: un fallo silencioso en la caja parece "no hay productos".
  const fail = msg => err => {
    toast.error(err?.response?.data?.detail || msg)
  }

  // El dueño elige qué caja mira; recepción siempre ve la suya.
  const contexto = verTodasLasSucursales ? sucursal : String(sucursalId ?? '')
  const q = contexto ? `?sucursal=${contexto}` : ''

  const loadProductos = useCallback(() =>
    api.get(`/tienda/productos/${q}`).then(r => setProductos(r.data)).catch(fail('No se pudo cargar el catálogo')), [q])
  const loadVentas = useCallback(() =>
    api.get(`/tienda/ventas/${q}`).then(r => setVentas(r.data)).catch(fail('No se pudieron cargar las ventas')), [q])
  const loadResumen = useCallback(() =>
    api.get(`/tienda/ventas/resumen/${q}`).then(r => setResumen(r.data)).catch(() => {}), [q])

  useEffect(() => {
    api.get('/gyms/sucursales/')
      .then(r => {
        setSucursales(r.data)
        const propia = r.data.find(s => s.id === sucursalId)
        if (propia) setSucursal(String(propia.id))
        else if (r.data.length) setSucursal(String(r.data[0].id))
      })
      .catch(fail('No se pudieron cargar las sucursales'))
  }, [sucursalId])

  // Cambiar de sucursal recarga catálogo y corte: el stock y las ventas son de un local.
  useEffect(() => {
    loadProductos()
    loadVentas()
    loadResumen()
  }, [loadProductos, loadVentas, loadResumen])

  const visibles = useMemo(() => {
    const q = busqueda.trim().toLowerCase()
    return productos.filter(p =>
      (catFiltro === 'todos' || p.categoria === catFiltro) &&
      (!q || p.nombre.toLowerCase().includes(q))
    )
  }, [productos, catFiltro, busqueda])

  const total = carrito.reduce((s, l) => s + Number(l.precio) * l.cantidad, 0)
  const piezas = carrito.reduce((s, l) => s + l.cantidad, 0)

  const agregar = producto => {
    if (producto.stock <= 0) return toast.error(`Sin stock de ${producto.nombre}`)
    setCarrito(prev => {
      const linea = prev.find(l => l.id === producto.id)
      if (!linea) return [...prev, { id: producto.id, nombre: producto.nombre, precio: producto.precio, cantidad: 1, stock: producto.stock }]
      if (linea.cantidad >= producto.stock) {
        toast.error(`Solo quedan ${producto.stock} de ${producto.nombre}`)
        return prev
      }
      return prev.map(l => l.id === producto.id ? { ...l, cantidad: l.cantidad + 1 } : l)
    })
  }

  const cambiarCantidad = (id, delta) => {
    setCarrito(prev => prev.flatMap(l => {
      if (l.id !== id) return [l]
      const nueva = l.cantidad + delta
      if (nueva <= 0) return []
      if (nueva > l.stock) { toast.error(`Solo quedan ${l.stock}`); return [l] }
      return [{ ...l, cantidad: nueva }]
    }))
  }

  const cobrar = async () => {
    if (!carrito.length) return
    if (!contexto) return toast.error('Selecciona la sucursal')
    setCobrando(true)
    try {
      const { data } = await api.post('/tienda/ventas/', {
        sucursal: Number(contexto),
        metodo,
        items: carrito.map(l => ({ producto: l.id, cantidad: l.cantidad })),
      })
      toast.success(`Venta #${data.id} cobrada · ${money(data.total)}`)
      setCarrito([])
      loadProductos()   // el stock cambió
      loadVentas()
      loadResumen()
    } catch (err) {
      const d = err?.response?.data
      toast.error(d?.items?.[0] || d?.sucursal?.[0] || d?.detail || 'No se pudo cobrar')
    } finally {
      setCobrando(false)
    }
  }

  const guardarProducto = async e => {
    e.preventDefault()
    setGuardando(true)
    try {
      const payload = { ...form, precio: form.precio || 0, costo: form.costo || 0 }
      if (form.id) {
        // El catálogo se edita entero; las existencias van por su propio endpoint,
        // porque son de una sucursal y no del producto.
        const {
          stock, stock_minimo,
          stock_por_sucursal: _sps, stock_total: _st, stock_bajo: _sb,
          ...catalogo
        } = payload
        await api.patch(`/tienda/productos/${form.id}/`, catalogo)
        if (contexto && (stock !== undefined || stock_minimo !== undefined)) {
          await api.post(`/tienda/productos/${form.id}/stock/`, {
            sucursal: Number(contexto),
            cantidad: Number(stock),
            stock_minimo: Number(stock_minimo),
          })
        }
        toast.success('Producto actualizado')
      } else {
        await api.post(`/tienda/productos/${q}`, payload)
        toast.success('Producto añadido')
      }
      setModal(false)
      setForm(EMPTY_PRODUCTO)
      loadProductos()
    } catch (err) {
      const d = err?.response?.data
      toast.error(typeof d === 'object' ? Object.values(d).flat()[0] : 'Error al guardar')
    } finally {
      setGuardando(false)
    }
  }

  const bajos = productos.filter(p => p.stock_bajo)

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-xl font-black text-white uppercase tracking-wide">PUNTO DE VENTA</h2>
          <p className="text-xs mt-0.5" style={{ color: '#8b949e' }}>
            {productos.length} productos{bajos.length > 0 && ` · ${bajos.length} con stock bajo`}
          </p>
        </div>
        <div className="flex gap-2 items-center flex-wrap">
          {verTodasLasSucursales && sucursales.length > 1 && (
            <select
              value={sucursal}
              onChange={e => setSucursal(e.target.value)}
              className="rounded-lg px-3 py-1.5 text-xs font-semibold"
              style={INPUT_STYLE}
            >
              {sucursales.map(s => <option key={s.id} value={s.id}>{s.nombre}</option>)}
            </select>
          )}
          {['caja', 'inventario', 'ventas'].map(t => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className="px-3 py-1.5 rounded-lg text-xs font-semibold capitalize transition-all"
              style={tab === t
                ? { backgroundColor: '#22c55e', color: '#0d1117' }
                : { backgroundColor: '#161b22', color: '#8b949e', border: '1px solid #21262d' }}
            >
              {t}
            </button>
          ))}
        </div>
      </div>

      {/* ---------------- CAJA ---------------- */}
      {tab === 'caja' && (
        <div className="grid gap-4 lg:grid-cols-[1fr_340px]">
          {/* Catálogo */}
          <div className="space-y-3">
            <div className="flex flex-wrap gap-2">
              <input
                value={busqueda}
                onChange={e => setBusqueda(e.target.value)}
                placeholder="Buscar producto..."
                className="rounded-lg px-3 py-2 text-sm flex-1 min-w-[180px] focus:outline-none"
                style={INPUT_STYLE}
              />
              {['todos', ...CATEGORIAS].map(c => (
                <button
                  key={c}
                  onClick={() => setCatFiltro(c)}
                  className="px-3 py-1.5 rounded-lg text-xs font-semibold transition-all"
                  style={catFiltro === c
                    ? { backgroundColor: '#22c55e', color: '#0d1117' }
                    : { backgroundColor: '#161b22', color: '#8b949e', border: '1px solid #21262d' }}
                >
                  {c === 'todos' ? 'Todos' : CAT_LABEL[c]}
                </button>
              ))}
            </div>

            <div className="grid gap-3 grid-cols-2 sm:grid-cols-3 xl:grid-cols-4">
              {visibles.map(p => (
                <button
                  key={p.id}
                  onClick={() => agregar(p)}
                  disabled={p.stock <= 0}
                  className="rounded-xl p-3 text-left transition-all disabled:opacity-40 disabled:cursor-not-allowed hover:brightness-125"
                  style={CARD_STYLE}
                >
                  <p className="text-xs font-bold text-white leading-tight">{p.nombre}</p>
                  <p className="text-[10px] mt-0.5" style={{ color: '#8b949e' }}>{CAT_LABEL[p.categoria]}</p>
                  <div className="flex items-baseline justify-between mt-2">
                    <span className="text-sm font-black" style={{ color: '#22c55e' }}>{money(p.precio)}</span>
                    <span className="text-[10px] font-semibold" style={{ color: p.stock_bajo ? '#f97316' : '#8b949e' }}>
                      {p.stock} pz
                    </span>
                  </div>
                </button>
              ))}
              {visibles.length === 0 && (
                <div className="col-span-full rounded-xl py-10 text-center text-xs" style={{ ...CARD_STYLE, color: '#3d444d' }}>
                  Sin productos
                </div>
              )}
            </div>
          </div>

          {/* Carrito */}
          <div className="rounded-xl p-4 h-fit lg:sticky lg:top-4 space-y-3" style={CARD_STYLE}>
            <div className="flex items-center justify-between">
              <h3 className="text-xs font-bold text-white tracking-widest">TICKET</h3>
              {carrito.length > 0 && (
                <button onClick={() => setCarrito([])} className="text-[10px] hover:text-white" style={{ color: '#8b949e' }}>
                  Vaciar
                </button>
              )}
            </div>

            <div className="space-y-2 max-h-[40vh] overflow-y-auto">
              {carrito.map(l => (
                <div key={l.id} className="flex items-center gap-2">
                  <div className="flex-1 min-w-0">
                    <p className="text-xs font-semibold text-white truncate">{l.nombre}</p>
                    <p className="text-[10px]" style={{ color: '#8b949e' }}>{money(l.precio)} c/u</p>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <button onClick={() => cambiarCantidad(l.id, -1)} className="w-6 h-6 rounded text-xs font-bold" style={{ backgroundColor: '#0d1117', color: '#8b949e' }}>−</button>
                    <span className="text-xs font-bold text-white w-5 text-center">{l.cantidad}</span>
                    <button onClick={() => cambiarCantidad(l.id, 1)} className="w-6 h-6 rounded text-xs font-bold" style={{ backgroundColor: '#0d1117', color: '#8b949e' }}>+</button>
                  </div>
                  <span className="text-xs font-bold text-white w-16 text-right">{money(Number(l.precio) * l.cantidad)}</span>
                </div>
              ))}
              {carrito.length === 0 && (
                <p className="text-xs py-6 text-center" style={{ color: '#3d444d' }}>Toca un producto para agregarlo</p>
              )}
            </div>

            <div style={{ borderTop: '1px solid #21262d' }} className="pt-3 space-y-3">
              <div className="flex items-baseline justify-between">
                <span className="text-[10px] tracking-widest" style={{ color: '#8b949e' }}>{piezas} PZ · TOTAL</span>
                <span className="text-xl font-black" style={{ color: '#22c55e' }}>{money(total)}</span>
              </div>

              <div className="grid grid-cols-3 gap-1.5">
                {METODOS.map(m => (
                  <button
                    key={m.v}
                    onClick={() => setMetodo(m.v)}
                    className="px-2 py-1.5 rounded-lg text-[10px] font-semibold transition-all"
                    style={metodo === m.v
                      ? { backgroundColor: '#22c55e', color: '#0d1117' }
                      : { backgroundColor: '#0d1117', color: '#8b949e', border: '1px solid #21262d' }}
                  >
                    {m.label}
                  </button>
                ))}
              </div>

              {sucursales.length > 1 && (
                <p className="text-[10px] text-center" style={{ color: '#8b949e' }}>
                  Caja de{' '}
                  <span className="text-white font-semibold">
                    {sucursales.find(s => String(s.id) === String(contexto))?.nombre || '—'}
                  </span>
                </p>
              )}

              <button
                onClick={cobrar}
                disabled={!carrito.length || cobrando}
                className="w-full py-2.5 rounded-lg text-xs font-bold transition-all disabled:opacity-40"
                style={{ backgroundColor: '#22c55e', color: '#0d1117' }}
              >
                {cobrando ? 'Cobrando...' : `Cobrar ${money(total)}`}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ---------------- INVENTARIO ---------------- */}
      {tab === 'inventario' && (
        <div className="space-y-3">
          {isAdmin && (
            <button
              onClick={() => { setForm(EMPTY_PRODUCTO); setModal(true) }}
              className="px-4 py-2.5 rounded-lg text-xs font-bold"
              style={{ backgroundColor: '#22c55e', color: '#0d1117' }}
            >
              + Añadir producto
            </button>
          )}
          <div className="rounded-xl overflow-hidden" style={CARD_STYLE}>
            <div className="overflow-x-auto">
              <table className="w-full text-sm min-w-[640px]">
                <thead style={{ borderBottom: '1px solid #21262d' }}>
                  <tr>
                    {['PRODUCTO', 'CATEGORÍA', 'PRECIO', 'COSTO', 'MARGEN', 'STOCK', ''].map(h => (
                      <th key={h} className="px-4 py-3 text-left text-[10px] font-bold tracking-widest" style={{ color: '#8b949e' }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {productos.map((p, i) => (
                    <tr key={p.id} style={{ borderBottom: i < productos.length - 1 ? '1px solid #21262d' : undefined }}>
                      <td className="px-4 py-3 text-xs font-semibold text-white">{p.nombre}</td>
                      <td className="px-4 py-3 text-xs" style={{ color: '#8b949e' }}>{CAT_LABEL[p.categoria]}</td>
                      <td className="px-4 py-3 text-xs font-bold text-white">{money(p.precio)}</td>
                      <td className="px-4 py-3 text-xs" style={{ color: '#8b949e' }}>{money(p.costo)}</td>
                      <td className="px-4 py-3 text-xs font-semibold" style={{ color: '#22c55e' }}>{money(p.precio - p.costo)}</td>
                      <td className="px-4 py-3 text-xs font-bold" style={{ color: p.stock_bajo ? '#f97316' : '#fff' }}>
                        {p.stock}{p.stock_bajo && ' ⚠'}
                        {/* Con varias sucursales, el número de arriba es el de la caja
                            que estás mirando; abajo va de dónde sale cada pieza. */}
                        {p.stock_por_sucursal?.length > 1 && (
                          <span className="block text-[10px] font-normal mt-0.5" style={{ color: '#8b949e' }}>
                            {p.stock_por_sucursal.map(s => `${s.sucursal_nombre}: ${s.cantidad}`).join(' · ')}
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-right">
                        {isAdmin && (
                          <button onClick={() => { setForm(p); setModal(true) }} style={{ color: '#8b949e' }} className="hover:text-white transition-colors">
                            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                            </svg>
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                  {productos.length === 0 && (
                    <tr><td colSpan={7} className="px-4 py-10 text-center text-xs" style={{ color: '#3d444d' }}>Sin productos</td></tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* ---------------- VENTAS ---------------- */}
      {tab === 'ventas' && (
        <div className="space-y-3">
          {resumen && (
            <div className="grid gap-3 grid-cols-2 lg:grid-cols-4">
              {[
                ['Vendido hoy', money(resumen.ventas_hoy)],
                ['Vendido este mes', money(resumen.ventas_mes)],
                ['Margen acumulado', money(resumen.margen)],
                ['Tickets', resumen.num_ventas],
              ].map(([label, valor]) => (
                <div key={label} className="rounded-xl p-4" style={CARD_STYLE}>
                  <p className="text-[10px] tracking-widest" style={{ color: '#8b949e' }}>{label.toUpperCase()}</p>
                  <p className="text-lg font-black text-white mt-1">{valor}</p>
                </div>
              ))}
            </div>
          )}
          <div className="rounded-xl overflow-hidden" style={CARD_STYLE}>
            <div className="overflow-x-auto">
              <table className="w-full text-sm min-w-[640px]">
                <thead style={{ borderBottom: '1px solid #21262d' }}>
                  <tr>
                    {['TICKET', 'FECHA', 'PRODUCTOS', 'MÉTODO', 'CAJERO', 'TOTAL'].map(h => (
                      <th key={h} className="px-4 py-3 text-left text-[10px] font-bold tracking-widest" style={{ color: '#8b949e' }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {ventas.map((v, i) => (
                    <tr key={v.id} style={{ borderBottom: i < ventas.length - 1 ? '1px solid #21262d' : undefined }}>
                      <td className="px-4 py-3 text-xs font-bold text-white">#{v.id}</td>
                      <td className="px-4 py-3 text-xs" style={{ color: '#8b949e' }}>{new Date(v.fecha).toLocaleString('es-MX')}</td>
                      <td className="px-4 py-3 text-xs" style={{ color: '#8b949e' }}>
                        {v.items.map(it => `${it.cantidad}× ${it.producto_nombre}`).join(', ')}
                      </td>
                      <td className="px-4 py-3 text-xs capitalize" style={{ color: '#8b949e' }}>{v.metodo}</td>
                      <td className="px-4 py-3 text-xs" style={{ color: '#8b949e' }}>{v.vendido_por_nombre || '—'}</td>
                      <td className="px-4 py-3 text-xs font-bold" style={{ color: '#22c55e' }}>{money(v.total)}</td>
                    </tr>
                  ))}
                  {ventas.length === 0 && (
                    <tr><td colSpan={6} className="px-4 py-10 text-center text-xs" style={{ color: '#3d444d' }}>Sin ventas</td></tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* ---------------- MODAL PRODUCTO ---------------- */}
      {modal && (
        <div className="fixed inset-0 flex items-center justify-center z-50 p-4" style={{ backgroundColor: 'rgba(0,0,0,0.7)' }}>
          <div className="rounded-2xl p-6 w-full max-w-md" style={CARD_STYLE}>
            <div className="flex items-center justify-between mb-5">
              <h2 className="text-sm font-bold text-white">{form.id ? 'Editar producto' : 'Añadir producto'}</h2>
              <button onClick={() => setModal(false)} style={{ color: '#8b949e' }} className="hover:text-white">
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" /></svg>
              </button>
            </div>
            <form onSubmit={guardarProducto} className="space-y-3">
              <label className="block">
                <span className="text-[10px] tracking-widest" style={{ color: '#8b949e' }}>NOMBRE</span>
                <input required value={form.nombre} onChange={e => setForm({ ...form, nombre: e.target.value })} className={inputCls} style={INPUT_STYLE} />
              </label>
              <label className="block">
                <span className="text-[10px] tracking-widest" style={{ color: '#8b949e' }}>CATEGORÍA</span>
                <select value={form.categoria} onChange={e => setForm({ ...form, categoria: e.target.value })} className={inputCls} style={INPUT_STYLE}>
                  {CATEGORIAS.map(c => <option key={c} value={c}>{CAT_LABEL[c]}</option>)}
                </select>
              </label>
              <div className="grid grid-cols-2 gap-3">
                <label className="block">
                  <span className="text-[10px] tracking-widest" style={{ color: '#8b949e' }}>PRECIO VENTA</span>
                  <input required type="number" step="0.01" min="0" value={form.precio} onChange={e => setForm({ ...form, precio: e.target.value })} className={inputCls} style={INPUT_STYLE} />
                </label>
                <label className="block">
                  <span className="text-[10px] tracking-widest" style={{ color: '#8b949e' }}>COSTO</span>
                  <input type="number" step="0.01" min="0" value={form.costo} onChange={e => setForm({ ...form, costo: e.target.value })} className={inputCls} style={INPUT_STYLE} />
                </label>
                {form.id ? (
                  <>
                    <label className="block">
                      <span className="text-[10px] tracking-widest" style={{ color: '#8b949e' }}>
                        STOCK EN {sucursales.find(s => String(s.id) === String(contexto))?.nombre?.toUpperCase() || 'SUCURSAL'}
                      </span>
                      <input type="number" min="0" value={form.stock ?? 0} onChange={e => setForm({ ...form, stock: e.target.value })} className={inputCls} style={INPUT_STYLE} />
                    </label>
                    <label className="block">
                      <span className="text-[10px] tracking-widest" style={{ color: '#8b949e' }}>STOCK MÍNIMO</span>
                      <input type="number" min="0" value={form.stock_minimo ?? 5} onChange={e => setForm({ ...form, stock_minimo: e.target.value })} className={inputCls} style={INPUT_STYLE} />
                    </label>
                  </>
                ) : (
                  <label className="block col-span-2">
                    <span className="text-[10px] tracking-widest" style={{ color: '#8b949e' }}>
                      STOCK INICIAL EN {sucursales.find(s => String(s.id) === String(contexto))?.nombre?.toUpperCase() || 'SUCURSAL'}
                    </span>
                    <input type="number" min="0" value={form.stock_inicial} onChange={e => setForm({ ...form, stock_inicial: e.target.value })} className={inputCls} style={INPUT_STYLE} />
                    <span className="block text-[10px] mt-1" style={{ color: '#3d444d' }}>
                      Las demás sucursales arrancan en 0 y se cargan desde su propia caja.
                    </span>
                  </label>
                )}
              </div>
              <button type="submit" disabled={guardando} className="w-full py-2.5 rounded-lg text-xs font-bold mt-2 disabled:opacity-40" style={{ backgroundColor: '#22c55e', color: '#0d1117' }}>
                {guardando ? 'Guardando...' : 'Guardar'}
              </button>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
