/**
 * Envío del código QR de un socio por WhatsApp.
 *
 * Vive fuera de la página porque decide a QUIÉN se le manda la credencial de acceso de
 * un socio y con qué contenido: es la lógica que más daño hace si se rompe en silencio
 * —un dígito de más en el teléfono manda el QR de alguien a un desconocido— y dentro de
 * un componente de 1300 líneas no había forma de fijarla con pruebas.
 *
 * Límite que condiciona todo el módulo: **un enlace de WhatsApp no puede adjuntar una
 * imagen**. `wa.me` y `web.whatsapp.com/send` solo aceptan teléfono y texto, así que el
 * QR llega o como enlace a la página que lo muestra, o pegado a mano desde el
 * portapapeles. No hay una tercera vía sin la API de negocios de Meta.
 */

// WhatsApp exige el número en formato internacional y sin signos. Los teléfonos se
// capturan como se dictan ("33 2233 2046"), así que aquí se normaliza: 10 dígitos son
// un número mexicano y se les antepone 52. Sin esto el enlace abre un chat vacío con
// un número que no existe y nadie se entera de que el QR nunca se envió.
export function telefonoWhatsApp(raw) {
  const digitos = String(raw || '').replace(/\D/g, '')
  if (digitos.length === 10) return `52${digitos}`
  // 12 (52 + 10) y 13 (521 + 10, el formato viejo de móviles) ya vienen con lada.
  if (digitos.length >= 11 && digitos.length <= 15) return digitos
  return null
}

// A quién se le manda: al socio, y al tutor solo si el socio no tiene teléfono propio.
// El caso que decide la regla es el menor: si el gym capturó su número es porque entrena
// solo y ese es el que sirve; si no lo tiene, su credencial la administra quien lo trae.
// Sea cual sea, el modal escribe el destinatario debajo del botón antes de abrir nada.
export function destinatarioWhatsApp(socio) {
  if (!socio?.codigo_acceso) return null
  const propio = telefonoWhatsApp(socio.telefono)
  if (propio) return { telefono: propio, nombre: socio.nombre, esTutor: false }
  const tutor = telefonoWhatsApp(socio.tutor_telefono)
  if (tutor) return { telefono: tutor, nombre: socio.tutor_nombre || 'su tutor', esTutor: true }
  return null
}

// El enlace al PNG solo se manda si el servidor es alcanzable desde el teléfono del
// socio. En desarrollo la URL apunta a localhost y mandarla sería darle al socio un
// enlace muerto; ahí el mensaje va sin ella y queda el pegado con Ctrl+V.
export function urlPublicaDelQR(url) {
  if (!url) return null
  try {
    const { hostname } = new URL(url)
    const privada = hostname === 'localhost'
      || hostname === '[::1]'
      || hostname.startsWith('127.')
      || hostname.startsWith('10.')
      || hostname.startsWith('192.168.')
      || /^172\.(1[6-9]|2\d|3[01])\./.test(hostname)
      || hostname.endsWith('.local')
    return privada ? null : url
  } catch {
    return null
  }
}

// Si al socio le falta aceptar el aviso de privacidad vigente. Es la misma regla que
// aplica la página del QR en el backend (`QRPaginaView._aviso_pendiente`): un
// consentimiento de una versión anterior no cuenta. Sin aviso publicado no hay nada
// que aceptar.
export function avisoPendiente(socio, aviso) {
  if (!socio || !aviso) return false
  return socio.consentimiento?.version !== aviso.version
}

export function mensajeQR(socio, destino, { avisoPendiente: pendiente = false } = {}) {
  const donde = socio.sucursal_nombre ? ` de ${socio.sucursal_nombre}` : ''
  const pagina = urlPublicaDelQR(socio.qr_pagina_url)
  // Con el aviso sin aceptar, el enlace abre primero el aviso y el QR sale después de
  // aceptarlo. El mensaje lo dice de entrada: si promete "tu código QR" y lo primero
  // que aparece es un texto legal, el socio cree que le mandaron otra cosa y lo cierra.
  if (pendiente && pagina) {
    const cuerpo = destino.esTutor
      ? `Hola, para ver el código QR de acceso de ${socio.nombre} ${socio.apellido} al gimnasio${donde} `
        + 'primero hay que aceptar nuestro aviso de privacidad.'
      : `Hola ${socio.nombre.split(' ')[0]}, para ver tu código QR de acceso al gimnasio${donde} `
        + 'primero necesitamos que aceptes nuestro aviso de privacidad.'
    return [
      cuerpo,
      `\nAceptar el aviso y ver ${destino.esTutor ? 'su' : 'tu'} código QR: ${pagina}`,
    ].join('\n')
  }
  const cuerpo = destino.esTutor
    ? `Hola, te comparto el código QR de acceso de ${socio.nombre} ${socio.apellido} al gimnasio${donde}. `
      + 'Con él registra su entrada.'
    : `Hola ${socio.nombre.split(' ')[0]}, te comparto tu código QR de acceso al gimnasio${donde}. `
      + 'Muéstralo en la entrada para registrar tu acceso.'
  // Con enlace se manda el enlace y nada más: el socio pulsa y ve su QR. El texto del
  // código solo va cuando NO hay enlace, porque entonces es lo único que le queda; de
  // otro modo sería pedirle que teclee una cadena de 30 caracteres en la puerta.
  //
  // El enlace va en su propia línea para que WhatsApp lo detecte y muestre la
  // miniatura del QR: pegado al texto lo deja como texto plano.
  return [
    cuerpo,
    pagina
      ? `\n${destino.esTutor ? 'Ver su' : 'Ver tu'} código QR: ${pagina}`
      : `\nCódigo: ${socio.codigo_acceso}`,
    // Sin enlace no hay página que pida el aviso, pero el socio igual tiene que saber
    // que le falta aceptarlo: si el mensaje calla, nadie se lo vuelve a pedir.
    pendiente && !pagina
      ? (destino.esTutor
        ? `\nFalta aceptar nuestro aviso de privacidad en nombre de ${socio.nombre}: pídelo en recepción.`
        : '\nFalta que aceptes nuestro aviso de privacidad: pídelo en recepción.')
      : null,
  ].filter(Boolean).join('\n')
}

// En el escritorio de recepción interesa WhatsApp Web, donde la sesión ya está abierta;
// en una tablet, el enlace corto que abre la app instalada.
export function urlWhatsApp(telefono, texto) {
  const t = encodeURIComponent(texto)
  return /Android|iPhone|iPad|iPod/i.test(navigator.userAgent)
    ? `https://wa.me/${telefono}?text=${t}`
    : `https://web.whatsapp.com/send?phone=${telefono}&text=${t}`
}
