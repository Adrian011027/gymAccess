"""Check-in por número de socio (1001, 1002…) además del token del QR.

El caso que resuelve es el de todos los días: el socio llega sin teléfono y sin
credencial. Antes recepción no tenía cómo registrarlo desde el kiosco y acababa
abriendo la puerta sin dejar rastro, que es justo lo que la bitácora existe para
evitar.

Lo que estas pruebas fijan es que el atajo NO se salta ninguna regla: el número
identifica al socio, y de ahí en adelante el check-in es exactamente el mismo.
"""

from datetime import date, timedelta

from django.utils import timezone
from rest_framework import status

from accesos.models import Acceso, MetodoAcceso
from gyms.models import Sucursal
from gyms.tests import BaseAPITestCase
from socios.models import Membresia, Plan, Socio

URL = '/api/accesos/checkin/'


class CodigoCortoBase(BaseAPITestCase):
    def setUp(self):
        super().setUp()
        self.plan = Plan.objects.create(
            gym=self.gym, nombre='Mensual', tipo='mensual', precio=500, duracion_dias=30,
        )
        self.socio = self.crear_socio('Ana', 'Lopez', 1001, token='TOKEN-ANA')

    def crear_socio(self, nombre, apellido, numero, token=None, sucursal=..., gym=None,
                    con_membresia=True, activo=True):
        socio = Socio.objects.create(
            gym=gym or self.gym, nombre=nombre, apellido=apellido,
            numero_socio=numero, activo=activo,
            sucursal=self.sucursal if sucursal is ... else sucursal,
        )
        if token:
            MetodoAcceso.objects.create(socio=socio, tipo='qr', token=token)
        if con_membresia:
            Membresia.objects.create(
                socio=socio, plan=self.plan, sucursal=socio.sucursal or self.sucursal,
                fecha_inicio=date.today(), fecha_fin=date.today() + timedelta(days=30),
                estado='activa',
            )
        return socio

    def checkin(self, codigo, sucursal=None, **extra):
        return self.client.post(URL, {
            'token': codigo, 'sucursal_id': (sucursal or self.sucursal).id, **extra,
        })


class CheckInPorNumeroDeSocioTests(CodigoCortoBase):
    def test_numero_de_socio_registra_el_acceso(self):
        resp = self.checkin('1001')

        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.assertEqual(resp.data['acceso'], 'permitido')
        self.assertEqual(resp.data['socio'], 'Ana Lopez')
        self.assertTrue(Acceso.objects.filter(socio=self.socio, resultado='permitido').exists())

    def test_el_token_del_qr_sigue_funcionando(self):
        resp = self.checkin('TOKEN-ANA')

        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.assertEqual(Acceso.objects.get(socio=self.socio).metodo_usado, 'qr')

    def test_entrada_tecleada_queda_como_manual_no_como_escaneo(self):
        """La bitácora tiene que distinguir quién llegó con su código y quién no.

        Si el número se anotara como 'qr', el reporte diría que todos escanean y
        nadie sabría cuánto trabajo manual se está haciendo en el mostrador.
        """
        self.checkin('1001')

        self.assertEqual(Acceso.objects.get(socio=self.socio).metodo_usado, 'manual')

    def test_socio_sin_qr_asignado_tambien_entra_por_su_numero(self):
        sin_qr = self.crear_socio('Beto', 'Ruiz', 1002)

        resp = self.checkin('1002')

        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.assertEqual(resp.data['socio'], 'Beto Ruiz')
        self.assertTrue(Acceso.objects.filter(socio=sin_qr, resultado='permitido').exists())

    def test_numero_inexistente_es_404(self):
        resp = self.checkin('9999')

        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
        self.assertFalse(Acceso.objects.exists())

    def test_codigo_vacio_es_404_y_no_revienta(self):
        resp = self.checkin('')

        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_numero_absurdamente_largo_no_llega_a_la_consulta(self):
        """Un PositiveIntegerField no aguanta 30 cifras: sin el tope, 500."""
        resp = self.checkin('1' * 30)

        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)


class NumeroNoSaltaNingunaReglaTests(CodigoCortoBase):
    """El número solo dice quién es. Todo lo que se comprobaba después se sigue
    comprobando: teclearlo no es una puerta de servicio."""

    def test_membresia_vencida_se_deniega_igual(self):
        Membresia.objects.filter(socio=self.socio).update(
            fecha_fin=date.today() - timedelta(days=1), estado='vencida',
        )

        resp = self.checkin('1001')

        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(Acceso.objects.get(socio=self.socio).motivo_denegado, 'membresia_vencida')

    def test_socio_dado_de_baja_se_deniega_igual(self):
        self.socio.activo = False
        self.socio.save(update_fields=['activo'])

        resp = self.checkin('1001')

        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(Acceso.objects.get(socio=self.socio).motivo_denegado, 'suspendido')

    def test_segunda_entrada_del_dia_se_deniega_igual(self):
        self.assertEqual(self.checkin('1001').status_code, status.HTTP_200_OK)

        resp = self.checkin('1001')

        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(resp.data['motivo'][:16], 'ya se registró s')

    def test_no_se_puede_mezclar_qr_y_numero_para_entrar_dos_veces(self):
        """Escanear y luego teclear es el mismo socio: la segunda no pasa."""
        self.assertEqual(self.checkin('TOKEN-ANA').status_code, status.HTTP_200_OK)

        resp = self.checkin('1001')

        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_socio_eliminado_logicamente_no_existe_para_el_numero(self):
        self.socio.eliminado_en = timezone.now()
        self.socio.save(update_fields=['eliminado_en'])

        resp = self.checkin('1001')

        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_politica_de_visitantes_se_aplica_igual(self):
        norte = Sucursal.objects.create(gym=self.gym, nombre='Norte')
        self.gym.politica_visitantes = 'bloqueado'
        self.gym.save(update_fields=['politica_visitantes'])

        resp = self.checkin('1001', sucursal=norte)

        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(Acceso.objects.get(socio=self.socio).motivo_denegado, 'otra_sucursal')


class NumeroAisladoPorGymTests(CodigoCortoBase):
    """El consecutivo se repite entre negocios: el 1001 existe en cada gym."""

    def test_el_1001_del_gym_de_al_lado_no_entra_aqui(self):
        otra_sucursal = Sucursal.objects.create(gym=self.otro_gym, nombre='Ajena')
        otro_plan = Plan.objects.create(
            gym=self.otro_gym, nombre='Mensual', tipo='mensual', precio=500, duracion_dias=30,
        )
        ajeno = Socio.objects.create(
            gym=self.otro_gym, nombre='Ajeno', apellido='X',
            numero_socio=1001, sucursal=otra_sucursal,
        )
        Membresia.objects.create(
            socio=ajeno, plan=otro_plan, sucursal=otra_sucursal,
            fecha_inicio=date.today(), fecha_fin=date.today() + timedelta(days=30),
            estado='activa',
        )

        resp = self.checkin('1001')

        # Entra el 1001 de ESTE gym, no el del otro.
        self.assertEqual(resp.data['socio'], 'Ana Lopez')
        self.assertFalse(Acceso.objects.filter(socio=ajeno).exists())


class BuscarSocioPorNumeroTests(CodigoCortoBase):
    """El buscador del kiosco también acepta el número: es el que recepción dicta."""

    def test_busqueda_por_numero_encuentra_al_socio(self):
        resp = self.client.get('/api/accesos/buscar-socio/?q=1001')

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data), 1)
        self.assertEqual(resp.data[0]['nombre'], 'Ana Lopez')
        self.assertEqual(resp.data[0]['numero_socio'], 1001)

    def test_la_busqueda_por_nombre_sigue_funcionando(self):
        resp = self.client.get('/api/accesos/buscar-socio/?q=ana')

        self.assertEqual([s['nombre'] for s in resp.data], ['Ana Lopez'])

    def test_numero_de_otro_gym_no_aparece(self):
        Socio.objects.create(gym=self.otro_gym, nombre='Ajeno', apellido='X', numero_socio=1001)

        resp = self.client.get('/api/accesos/buscar-socio/?q=1001')

        self.assertEqual(len(resp.data), 1)
        self.assertEqual(resp.data[0]['nombre'], 'Ana Lopez')

    def test_numero_inexistente_devuelve_lista_vacia(self):
        resp = self.client.get('/api/accesos/buscar-socio/?q=8888')

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data, [])


class QRImagenPublicaTests(CodigoCortoBase):
    """El PNG del QR servido en una URL abrible sin sesión.

    Es lo que permite que el mensaje de WhatsApp lleve la imagen: un enlace de chat
    (`wa.me`) solo admite texto, así que la única forma de que el socio reciba el
    código sin que recepción lo pegue a mano es un enlace que él pueda abrir.

    Pública no significa descuidada: lo que se comprueba aquí es que un QR revocado,
    de un socio de baja o borrado, deja de entregarse.
    """

    def url_de(self, token):
        return f'/api/accesos/qr/{token}.png'

    def test_devuelve_un_png_sin_necesidad_de_sesion(self):
        anonimo = self.client_class()

        resp = anonimo.get(self.url_de('TOKEN-ANA'))

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp['Content-Type'], 'image/png')
        # Firma de PNG: si devolviera un JSON de error el status ya sería otro, pero
        # esto fija que lo servido es de verdad una imagen.
        self.assertEqual(resp.content[:8], b'\x89PNG\r\n\x1a\n')

    def test_no_filtra_a_quien_pertenece_el_codigo(self):
        resp = self.client_class().get(self.url_de('TOKEN-ANA'))

        self.assertNotIn(b'Ana', resp.content[:2000])
        self.assertNotIn('socio', {k.lower() for k in resp.headers})

    def test_token_inexistente_es_404(self):
        resp = self.client_class().get(self.url_de('NO-EXISTE'))

        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_qr_revocado_deja_de_servirse(self):
        """Reasignar el QR invalida el anterior: el enlace viejo no puede seguir
        entregando una credencial que ya no abre la puerta."""
        MetodoAcceso.objects.filter(token='TOKEN-ANA').update(activo=False)

        resp = self.client_class().get(self.url_de('TOKEN-ANA'))

        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_socio_dado_de_baja_no_entrega_su_qr(self):
        self.socio.activo = False
        self.socio.save(update_fields=['activo'])

        resp = self.client_class().get(self.url_de('TOKEN-ANA'))

        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_socio_eliminado_no_entrega_su_qr(self):
        self.socio.eliminado_en = timezone.now()
        self.socio.save(update_fields=['eliminado_en'])

        resp = self.client_class().get(self.url_de('TOKEN-ANA'))

        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_el_socio_trae_la_url_de_su_qr_en_el_listado(self):
        socio = next(
            s for s in self.client.get('/api/socios/').data if s['id'] == self.socio.id
        )

        self.assertEqual(socio['codigo_acceso'], 'TOKEN-ANA')
        self.assertTrue(socio['qr_imagen_url'].endswith('/api/accesos/qr/TOKEN-ANA.png'))
        # Absoluta: un enlace relativo en el chat del socio no lleva a ningún lado.
        self.assertTrue(socio['qr_imagen_url'].startswith('http'))

    def test_socio_sin_qr_no_trae_url(self):
        Socio.objects.create(gym=self.gym, nombre='Sin', apellido='Codigo', numero_socio=1099)

        socio = next(
            s for s in self.client.get('/api/socios/').data if s['nombre'] == 'Sin'
        )

        self.assertIsNone(socio['qr_imagen_url'])


class QRPaginaPublicaTests(CodigoCortoBase):
    """La página que abre el socio al pulsar el enlace del chat.

    Es la que se comparte, y no el `.png` suelto, porque varios navegadores móviles
    descargan una URL de imagen en vez de mostrarla: el socio acabaría con un archivo
    en Descargas en vez de un código en pantalla al llegar a la puerta.
    """

    def url_de(self, token):
        return f'/api/accesos/qr/{token}/'

    def test_muestra_el_qr_sin_necesidad_de_sesion(self):
        resp = self.client_class().get(self.url_de('TOKEN-ANA'))

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn('text/html', resp['Content-Type'])
        self.assertIn('/api/accesos/qr/TOKEN-ANA.png', resp.content.decode())

    def test_lleva_og_image_para_que_whatsapp_muestre_la_miniatura(self):
        """Sin `og:image` el chat enseña un enlace pelado y el socio no ve nada del QR
        hasta abrirlo, que es justo la fricción que este enlace viene a quitar."""
        html = self.client_class().get(self.url_de('TOKEN-ANA')).content.decode()

        self.assertIn('property="og:image"', html)
        self.assertIn('/api/accesos/qr/TOKEN-ANA.png', html.split('og:image')[1][:200])

    def test_no_publica_el_nombre_del_socio(self):
        """El enlace se reenvía con un toque: lo único que debe viajar es el código."""
        html = self.client_class().get(self.url_de('TOKEN-ANA')).content.decode()

        self.assertNotIn('Ana', html)
        self.assertNotIn('Lopez', html)

    def test_qr_revocado_muestra_aviso_y_404(self):
        MetodoAcceso.objects.filter(token='TOKEN-ANA').update(activo=False)

        resp = self.client_class().get(self.url_de('TOKEN-ANA'))

        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn('ya no está disponible', resp.content.decode())

    def test_socio_de_baja_no_muestra_su_qr(self):
        self.socio.activo = False
        self.socio.save(update_fields=['activo'])

        self.assertEqual(
            self.client_class().get(self.url_de('TOKEN-ANA')).status_code,
            status.HTTP_404_NOT_FOUND,
        )

    def test_el_socio_trae_la_url_de_la_pagina_en_el_listado(self):
        socio = next(
            s for s in self.client.get('/api/socios/').data if s['id'] == self.socio.id
        )

        self.assertTrue(socio['qr_pagina_url'].endswith('/api/accesos/qr/TOKEN-ANA/'))
        self.assertTrue(socio['qr_pagina_url'].startswith('http'))

    def test_asignar_qr_devuelve_ya_la_pagina_para_compartir(self):
        """El modal manda el QR justo después de asignarlo: si la URL no viniera en esa
        respuesta, el enlace saldría vacío hasta recargar el listado."""
        sin_qr = self.crear_socio('Beto', 'Ruiz', 1002)

        resp = self.client.post('/api/accesos/asignar-qr/', {'socio_id': sin_qr.id})

        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        self.assertTrue(resp.data['pagina_url'].endswith(f"/api/accesos/qr/{resp.data['token']}/"))
        self.assertTrue(resp.data['imagen_url'].endswith(f"/api/accesos/qr/{resp.data['token']}.png"))


class QRBaseURLTests(CodigoCortoBase):
    """`QR_BASE_URL` fuerza el dominio del enlace que se manda al socio.

    El desajuste que arregla no se ve hasta que el socio recibe el mensaje: el enlace
    lo genera la petición de recepción, pero lo abre un teléfono de fuera. Si recepción
    entra por `localhost`, el enlace sale apuntando al propio teléfono del socio.
    """

    def test_sin_configurar_usa_el_host_de_la_peticion(self):
        socio = next(
            s for s in self.client.get('/api/socios/').data if s['id'] == self.socio.id
        )

        self.assertTrue(socio['qr_pagina_url'].startswith('http://testserver/'))

    def test_configurada_manda_el_enlace_al_dominio_publico(self):
        with self.settings(QR_BASE_URL='https://gym.example.com'):
            socio = next(
                s for s in self.client.get('/api/socios/').data if s['id'] == self.socio.id
            )

        self.assertEqual(
            socio['qr_pagina_url'], 'https://gym.example.com/api/accesos/qr/TOKEN-ANA/',
        )
        self.assertEqual(
            socio['qr_imagen_url'], 'https://gym.example.com/api/accesos/qr/TOKEN-ANA.png',
        )

    def test_la_pagina_incrusta_el_png_con_el_mismo_dominio(self):
        """Si la página usara el host de la petición y el enlace el configurado, el
        socio abriría un dominio público que le pide la imagen a una dirección
        interna: página en blanco."""
        with self.settings(QR_BASE_URL='https://gym.example.com'):
            html = self.client_class().get('/api/accesos/qr/TOKEN-ANA/').content.decode()

        self.assertIn('https://gym.example.com/api/accesos/qr/TOKEN-ANA.png', html)
        self.assertNotIn('http://testserver', html)

    def test_asignar_qr_tambien_respeta_el_dominio(self):
        sin_qr = self.crear_socio('Beto', 'Ruiz', 1002)

        with self.settings(QR_BASE_URL='https://gym.example.com'):
            resp = self.client.post('/api/accesos/asignar-qr/', {'socio_id': sin_qr.id})

        self.assertTrue(resp.data['pagina_url'].startswith('https://gym.example.com/'))
