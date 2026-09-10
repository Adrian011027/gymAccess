/**
 * Regresión del envío del QR por WhatsApp.
 *
 * Esta lógica decide a qué número se manda la credencial de acceso de un socio. Un
 * fallo aquí no da error en pantalla: abre el chat equivocado, o uno vacío, y nadie se
 * entera hasta que alguien entra al gimnasio con el QR de otro. De ahí que se fije caso
 * por caso en vez de confiar en probarlo a mano.
 */

import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  destinatarioWhatsApp, mensajeQR, telefonoWhatsApp, urlPublicaDelQR, urlWhatsApp,
} from './whatsappQR'

const socioBase = {
  nombre: 'Jose',
  apellido: 'Sanchez',
  telefono: '3322332046',
  codigo_acceso: 'R3B-QR-00030-N87LmCpAxTZCT0Hj',
  sucursal_nombre: 'Estrella',
}

function conUA(ua, fn) {
  // `navigator` es de solo lectura en Node: hay que redefinirlo, no asignarlo. Con una
  // asignación normal la prueba pasa sin llegar a cambiar el agente y no comprueba nada.
  const original = Object.getOwnPropertyDescriptor(globalThis, 'navigator')
  Object.defineProperty(globalThis, 'navigator', {
    value: { userAgent: ua }, configurable: true, writable: true,
  })
  try {
    return fn()
  } finally {
    if (original) Object.defineProperty(globalThis, 'navigator', original)
    else delete globalThis.navigator
  }
}

describe('telefonoWhatsApp', () => {
  it('antepone la lada de México a un número de 10 dígitos', () => {
    expect(telefonoWhatsApp('3322332046')).toBe('523322332046')
  })

  it('ignora espacios, guiones y paréntesis, que es como se capturan', () => {
    expect(telefonoWhatsApp('33 2233 2046')).toBe('523322332046')
    expect(telefonoWhatsApp('(33) 2233-2046')).toBe('523322332046')
    expect(telefonoWhatsApp('+52 33 2233 2046')).toBe('523322332046')
  })

  it('respeta los números que ya traen lada de país', () => {
    expect(telefonoWhatsApp('5213322332046')).toBe('5213322332046')
    expect(telefonoWhatsApp('+1 305 555 0199')).toBe('13055550199')
    expect(telefonoWhatsApp('+34 612 345 678')).toBe('34612345678')
  })

  it('devuelve null en vez de inventar una lada cuando el número no sirve', () => {
    // Un teléfono a medias con un 52 delante abre un chat con alguien que no es el
    // socio; es preferible dejar el botón deshabilitado.
    expect(telefonoWhatsApp('55512345')).toBeNull()
    expect(telefonoWhatsApp('no tiene')).toBeNull()
    expect(telefonoWhatsApp('')).toBeNull()
    expect(telefonoWhatsApp(null)).toBeNull()
    expect(telefonoWhatsApp(undefined)).toBeNull()
  })
})

describe('destinatarioWhatsApp', () => {
  it('manda al socio cuando tiene teléfono propio', () => {
    const d = destinatarioWhatsApp(socioBase)
    expect(d).toMatchObject({ telefono: '523322332046', nombre: 'Jose', esTutor: false })
  })

  it('cae al tutor solo si el socio no tiene teléfono', () => {
    const d = destinatarioWhatsApp({
      ...socioBase, telefono: '', tutor_telefono: '3312345678', tutor_nombre: 'María P.',
    })
    expect(d).toMatchObject({ telefono: '523312345678', nombre: 'María P.', esTutor: true })
  })

  it('un menor con teléfono propio recibe su QR él, no su tutor', () => {
    // La regla anterior mandaba siempre al tutor: si el gym capturó el número del
    // menor es porque entrena solo y ese es el que sirve.
    const d = destinatarioWhatsApp({
      ...socioBase, telefono: '3399999999', tutor_telefono: '3312345678',
      tutor_nombre: 'María P.', es_menor: true,
    })
    expect(d).toMatchObject({ telefono: '523399999999', esTutor: false })
  })

  it('sin ningún teléfono no hay destinatario', () => {
    expect(destinatarioWhatsApp({ ...socioBase, telefono: '' })).toBeNull()
    expect(destinatarioWhatsApp({ ...socioBase, telefono: 'no aplica' })).toBeNull()
  })

  it('sin código asignado no hay nada que mandar', () => {
    expect(destinatarioWhatsApp({ ...socioBase, codigo_acceso: null })).toBeNull()
  })

  it('no revienta con null', () => {
    expect(destinatarioWhatsApp(null)).toBeNull()
    expect(destinatarioWhatsApp(undefined)).toBeNull()
  })
})

describe('urlPublicaDelQR', () => {
  it('acepta un dominio público', () => {
    const url = 'https://gym.tudominio.com/api/accesos/qr/TOKEN/'
    expect(urlPublicaDelQR(url)).toBe(url)
  })

  it('descarta direcciones que el teléfono del socio no puede abrir', () => {
    // Es el fallo que no se ve al probar: el enlace se genera desde la sesión de
    // recepción, así que apunta a donde está recepción, no a donde está el socio.
    for (const url of [
      'http://localhost:5173/api/accesos/qr/T/',
      'http://127.0.0.1:8001/api/accesos/qr/T/',
      'http://192.168.1.40:8001/api/accesos/qr/T/',
      'http://10.0.0.5/api/accesos/qr/T/',
      'http://172.16.3.9/api/accesos/qr/T/',
      'http://mac-recepcion.local/api/accesos/qr/T/',
    ]) {
      expect(urlPublicaDelQR(url), url).toBeNull()
    }
  })

  it('no confunde un dominio público que empieza igual que uno privado', () => {
    // 172.15 y 172.32 quedan fuera del rango privado; un regex descuidado los tumbaba.
    expect(urlPublicaDelQR('http://172.15.0.1/api/accesos/qr/T/')).not.toBeNull()
    expect(urlPublicaDelQR('http://172.32.0.1/api/accesos/qr/T/')).not.toBeNull()
    expect(urlPublicaDelQR('https://127api.example.com/qr/')).not.toBeNull()
  })

  it('trata lo que no es una URL como si no hubiera enlace', () => {
    expect(urlPublicaDelQR(null)).toBeNull()
    expect(urlPublicaDelQR('')).toBeNull()
    expect(urlPublicaDelQR('no-es-una-url')).toBeNull()
  })
})

describe('mensajeQR', () => {
  const publica = 'https://gym.tudominio.com/api/accesos/qr/R3B-QR-00030-N87LmCpAxTZCT0Hj/'

  it('con enlace manda el enlace y NO el código en texto', () => {
    // Pedirle al socio que teclee 30 caracteres en la puerta no es una alternativa.
    const socio = { ...socioBase, qr_pagina_url: publica }
    const texto = mensajeQR(socio, destinatarioWhatsApp(socio))

    expect(texto).toContain(publica)
    expect(texto).not.toContain('Código: R3B-QR')
    expect(texto).toContain('Hola Jose')
  })

  it('sin enlace público cae al código, que es lo único que queda', () => {
    const socio = { ...socioBase, qr_pagina_url: 'http://127.0.0.1:8001/api/accesos/qr/T/' }
    const texto = mensajeQR(socio, destinatarioWhatsApp(socio))

    expect(texto).toContain('Código: R3B-QR-00030-N87LmCpAxTZCT0Hj')
    expect(texto).not.toContain('127.0.0.1')
  })

  it('el enlace va en su propia línea para que WhatsApp lo previsualice', () => {
    const socio = { ...socioBase, qr_pagina_url: publica }
    const lineaDelEnlace = mensajeQR(socio, destinatarioWhatsApp(socio))
      .split('\n').find(l => l.includes(publica))

    expect(lineaDelEnlace).toBe(`Ver tu código QR: ${publica}`)
  })

  it('al tutor se le habla del socio en tercera persona', () => {
    const socio = {
      ...socioBase, telefono: '', tutor_telefono: '3312345678',
      tutor_nombre: 'María P.', qr_pagina_url: publica,
    }
    const texto = mensajeQR(socio, destinatarioWhatsApp(socio))

    expect(texto).toContain('el código QR de acceso de Jose Sanchez')
    expect(texto).toContain('Ver su código QR:')
    expect(texto).not.toContain('Hola Jose')
  })

  it('usa solo el primer nombre al saludar', () => {
    const socio = { ...socioBase, nombre: 'Ana Sofía', qr_pagina_url: publica }
    expect(mensajeQR(socio, destinatarioWhatsApp(socio))).toContain('Hola Ana,')
  })

  it('omite la sucursal si el socio no tiene una asignada', () => {
    const socio = { ...socioBase, sucursal_nombre: null, qr_pagina_url: publica }
    expect(mensajeQR(socio, destinatarioWhatsApp(socio))).toContain('al gimnasio.')
  })
})

describe('urlWhatsApp', () => {
  afterEach(() => vi.restoreAllMocks())

  it('en el escritorio de recepción abre WhatsApp Web, donde ya hay sesión', () => {
    const url = conUA('Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120',
      () => urlWhatsApp('523322332046', 'hola'))
    expect(url).toBe('https://web.whatsapp.com/send?phone=523322332046&text=hola')
  })

  it('en móvil y tablet usa el enlace corto, que abre la app instalada', () => {
    for (const ua of [
      'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)',
      'Mozilla/5.0 (iPad; CPU OS 17_0 like Mac OS X)',
      'Mozilla/5.0 (Linux; Android 14)',
    ]) {
      expect(conUA(ua, () => urlWhatsApp('523322332046', 'hola')), ua)
        .toBe('https://wa.me/523322332046?text=hola')
    }
  })

  it('escapa el texto: saltos de línea y & romperían la query', () => {
    const url = conUA('Chrome', () => urlWhatsApp('52333', 'a&b\nc d'))
    expect(url).toContain('text=a%26b%0Ac%20d')
  })
})
