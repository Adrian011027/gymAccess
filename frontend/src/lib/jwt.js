/**
 * Decodifica el payload de un JWT sin verificar la firma (de eso se encarga el backend;
 * aquí sólo se lee el rol para pintar la interfaz).
 *
 * Devuelve null ante cualquier token que no sirva. Antes esto se hacía inline con un
 * JSON.parse(atob(...)) sin protección: un token corrupto en localStorage reventaba al
 * arrancar la app y dejaba la pantalla en blanco, sin forma de salir salvo limpiar el
 * navegador a mano.
 */
export function leerToken(token) {
  if (typeof token !== 'string') return null
  try {
    const payload = JSON.parse(atob(token.split('.')[1]))
    return payload?.rol ? payload : null
  } catch {
    return null
  }
}
