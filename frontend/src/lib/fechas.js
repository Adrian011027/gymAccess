/**
 * Fechas LOCALES en formato YYYY-MM-DD, que es como viaja una fecha sin hora en toda
 * la API (`fecha_inicio`, `fecha_fin`, el día del corte).
 *
 * `toISOString()` convierte a UTC: en México (UTC-6) a partir de las 18:00 devuelve el
 * día SIGUIENTE. Ese desfase de seis horas ya había mordido tres veces —el corte se
 * abría en el día de mañana vacío justo a la hora de cerrar la caja, la membresía
 * recién pagada empezaba mañana y el check-in rechazaba al socio, y "hoy" en Pagos
 * marcaba como "Atrasado 1 día" lo que vence hoy—, y cada sitio lo arregló por su
 * cuenta con una copia local. De ahí que este módulo exista: las copias no cubrían
 * todos los cálculos del mismo archivo.
 */

export const fechaLocal = (d = new Date()) =>
  new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 10)

export const hoyLocal = () => fechaLocal()

/** Hoy ± días. `setDate` y no sumar milisegundos: cruza meses y cambios de horario. */
export const enDias = dias => {
  const d = new Date()
  d.setDate(d.getDate() + dias)
  return fechaLocal(d)
}
