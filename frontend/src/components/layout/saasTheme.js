/**
 * Paleta de la consola del SaaS.
 *
 * Vive aparte del componente para no romper el fast-refresh (un archivo que exporta
 * componentes y constantes a la vez pierde el hot reload), y deliberadamente NO es la
 * del gimnasio: el índigo contra el verde es la señal de que estás una capa más
 * arriba, operando *sobre* los clientes en vez de dentro de uno.
 */
export const T = {
  fondo: '#080a12',
  panel: '#111527',
  panelAlto: '#161b32',
  borde: '#242b47',
  bordeSuave: '#1b2138',
  texto: '#e6e8f5',
  tenue: '#8b93b8',
  apagado: '#5a6188',
  acento: '#818cf8',
  acentoFuerte: '#6366f1',
  ok: '#34d399',
  alerta: '#fb7185',
  aviso: '#fbbf24',
}
