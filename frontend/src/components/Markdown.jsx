/**
 * Renderizador mínimo de Markdown, sin dependencias.
 *
 * Los documentos legales se leen de corrido: encabezados, párrafos, listas, tablas
 * y negritas cubren todo lo que traen los borradores. Traer una librería entera para
 * esto añadiría ~100 kB al bundle a cambio de nada que aquí se note.
 *
 * No interpreta HTML embebido a propósito: el texto lo escribe el admin del gym y
 * renderizarlo como HTML sería una inyección con su propia interfaz de edición.
 */

function Inline({ texto }) {
  // **negrita** y `código`. Se parte por los delimitadores conservándolos para no
  // perder el texto que va entre ellos.
  const partes = texto.split(/(\*\*[^*]+\*\*|`[^`]+`)/g)
  return (
    <>
      {partes.map((p, i) => {
        if (p.startsWith('**') && p.endsWith('**')) {
          return <strong key={i} className="text-white font-semibold">{p.slice(2, -2)}</strong>
        }
        if (p.startsWith('`') && p.endsWith('`')) {
          return (
            <code key={i} className="text-[11px] px-1 py-0.5 rounded font-mono"
              style={{ backgroundColor: '#0d1117', color: '#22c55e' }}>
              {p.slice(1, -1)}
            </code>
          )
        }
        return <span key={i}>{p}</span>
      })}
    </>
  )
}

export default function Markdown({ texto = '' }) {
  const lineas = texto.split('\n')
  const bloques = []
  let i = 0

  while (i < lineas.length) {
    const linea = lineas[i]

    if (!linea.trim()) { i++; continue }

    if (linea.startsWith('#')) {
      const nivel = linea.match(/^#+/)[0].length
      const contenido = linea.replace(/^#+\s*/, '')
      const tam = nivel === 1 ? 'text-base' : nivel === 2 ? 'text-sm' : 'text-xs'
      bloques.push(
        <h3 key={i} className={`${tam} font-bold text-white mt-5 mb-2 first:mt-0`}>
          <Inline texto={contenido} />
        </h3>
      )
      i++
      continue
    }

    // Cita: se usa en los borradores para las advertencias de "revisión legal".
    if (linea.startsWith('>')) {
      const cita = []
      while (i < lineas.length && lineas[i].startsWith('>')) {
        cita.push(lineas[i].replace(/^>\s?/, ''))
        i++
      }
      bloques.push(
        <blockquote key={i} className="text-xs leading-relaxed my-3 pl-3 py-2 rounded-r"
          style={{ borderLeft: '3px solid #f97316', backgroundColor: 'rgba(249,115,22,0.06)', color: '#8b949e' }}>
          <Inline texto={cita.join(' ')} />
        </blockquote>
      )
      continue
    }

    if (/^\|/.test(linea)) {
      const filas = []
      while (i < lineas.length && /^\|/.test(lineas[i])) {
        filas.push(lineas[i])
        i++
      }
      // La segunda fila del formato es el separador (|---|---|): no es contenido.
      const celdas = f => f.split('|').slice(1, -1).map(c => c.trim())
      const cabecera = celdas(filas[0])
      const cuerpo = filas.slice(2).map(celdas)
      bloques.push(
        <div key={i} className="my-3 overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr style={{ borderBottom: '1px solid #21262d' }}>
                {cabecera.map((c, j) => (
                  <th key={j} className="px-2 py-1.5 text-left font-bold" style={{ color: '#8b949e' }}>
                    <Inline texto={c} />
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {cuerpo.map((fila, j) => (
                <tr key={j} style={{ borderBottom: '1px solid #21262d' }}>
                  {fila.map((c, k) => (
                    <td key={k} className="px-2 py-1.5 align-top" style={{ color: '#8b949e' }}>
                      <Inline texto={c} />
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )
      continue
    }

    if (/^\s*[-*]\s/.test(linea) || /^\s*\d+\.\s/.test(linea)) {
      const ordenada = /^\s*\d+\.\s/.test(linea)
      const items = []
      while (i < lineas.length && (/^\s*[-*]\s/.test(lineas[i]) || /^\s*\d+\.\s/.test(lineas[i]))) {
        items.push(lineas[i].replace(/^\s*(?:[-*]|\d+\.)\s/, ''))
        i++
      }
      const Lista = ordenada ? 'ol' : 'ul'
      bloques.push(
        <Lista key={i} className={`text-xs leading-relaxed my-2 pl-5 space-y-1 ${ordenada ? 'list-decimal' : 'list-disc'}`}
          style={{ color: '#8b949e' }}>
          {items.map((it, j) => <li key={j}><Inline texto={it} /></li>)}
        </Lista>
      )
      continue
    }

    if (/^-{3,}$/.test(linea.trim())) {
      bloques.push(<hr key={i} className="my-4" style={{ borderColor: '#21262d' }} />)
      i++
      continue
    }

    // Párrafo: se juntan las líneas seguidas, como manda Markdown.
    const parrafo = []
    while (
      i < lineas.length && lineas[i].trim() &&
      !lineas[i].startsWith('#') && !lineas[i].startsWith('>') && !/^\|/.test(lineas[i]) &&
      !/^\s*[-*]\s/.test(lineas[i]) && !/^\s*\d+\.\s/.test(lineas[i]) &&
      !/^-{3,}$/.test(lineas[i].trim())
    ) {
      parrafo.push(lineas[i])
      i++
    }
    bloques.push(
      <p key={i} className="text-xs leading-relaxed my-2" style={{ color: '#8b949e' }}>
        <Inline texto={parrafo.join(' ')} />
      </p>
    )
  }

  return <div>{bloques}</div>
}
