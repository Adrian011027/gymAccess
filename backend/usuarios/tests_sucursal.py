from datetime import date, timedelta
from decimal import Decimal

from django.core.cache import cache
from rest_framework import status

from accesos.models import Acceso, MetodoAcceso
from gyms.models import Sucursal
from gyms.tests import BaseAPITestCase
from socios.models import Membresia, Pago, Plan, Socio
from tienda.models import StockSucursal, Venta
from tienda.tests import crear_producto
from usuarios.models import Usuario


class BaseDosSucursales(BaseAPITestCase):
    """Un gym con dos locales: el dueño ve ambos, cada recepción solo el suyo."""

    def setUp(self):
        super().setUp()
        self.centro = self.sucursal                     # 'Centro', de BaseAPITestCase
        self.norte = Sucursal.objects.create(gym=self.gym, nombre='Norte')

        self.duenio = self.user                          # rol admin, sucursal=None
        self.recep_centro = Usuario.objects.create_user(
            email='centro@round3.com', password='Passw0rd1', nombre='Rec Centro',
            rol='recepcion', gym=self.gym, sucursal=self.centro,
        )
        self.recep_norte = Usuario.objects.create_user(
            email='norte@round3.com', password='Passw0rd1', nombre='Rec Norte',
            rol='recepcion', gym=self.gym, sucursal=self.norte,
        )

        self.plan = Plan.objects.create(
            gym=self.gym, nombre='Mensual', tipo='mensual', precio=500, duracion_dias=30,
        )

    def socio_en(self, sucursal, nombre):
        socio = Socio.objects.create(
            gym=self.gym, sucursal=sucursal, nombre=nombre, apellido='Test',
        )
        membresia = Membresia.objects.create(
            socio=socio, plan=self.plan, sucursal=sucursal,
            fecha_inicio=date.today() - timedelta(days=1),
            fecha_fin=date.today() + timedelta(days=30),
            estado='activa',
        )
        MetodoAcceso.objects.create(socio=socio, tipo='qr', token=f'QR-{nombre}')
        return socio, membresia


class AlcanceLecturaTests(BaseDosSucursales):
    def test_duenio_ve_las_dos_sucursales(self):
        self.socio_en(self.centro, 'AnaCentro')
        self.socio_en(self.norte, 'BetoNorte')
        resp = self.client.get('/api/socios/membresias/')
        self.assertEqual(len(resp.data), 2)

    def test_recepcion_solo_ve_su_sucursal(self):
        self.socio_en(self.centro, 'AnaCentro')
        self.socio_en(self.norte, 'BetoNorte')
        self.authenticate(self.recep_norte)
        resp = self.client.get('/api/socios/membresias/')
        self.assertEqual(len(resp.data), 1)
        self.assertEqual(resp.data[0]['socio_nombre'], 'BetoNorte Test')

    def test_membresia_de_otra_sucursal_da_404(self):
        _, membresia = self.socio_en(self.centro, 'AnaCentro')
        self.authenticate(self.recep_norte)
        resp = self.client.get(f'/api/socios/membresias/{membresia.id}/')
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_socios_NO_se_acotan_por_sucursal(self):
        """El socio le paga al negocio: toda caja debe poder atenderlo."""
        self.socio_en(self.centro, 'AnaCentro')
        self.socio_en(self.norte, 'BetoNorte')
        self.authenticate(self.recep_norte)
        resp = self.client.get('/api/socios/')
        nombres = [s['nombre'] for s in resp.data]
        self.assertIn('AnaCentro', nombres)
        self.assertIn('BetoNorte', nombres)

    def test_socio_expone_de_que_sucursal_es(self):
        socio, _ = self.socio_en(self.centro, 'AnaCentro')
        self.authenticate(self.recep_norte)
        resp = self.client.get(f'/api/socios/{socio.id}/')
        self.assertEqual(resp.data['sucursal_nombre'], 'Centro')

    def test_accesos_acotados(self):
        socio_c, m_c = self.socio_en(self.centro, 'AnaCentro')
        socio_n, m_n = self.socio_en(self.norte, 'BetoNorte')
        Acceso.objects.create(socio=socio_c, sucursal=self.centro, membresia=m_c, resultado='permitido')
        Acceso.objects.create(socio=socio_n, sucursal=self.norte, membresia=m_n, resultado='permitido')

        self.assertEqual(len(self.client.get('/api/accesos/').data), 2)
        self.authenticate(self.recep_norte)
        resp = self.client.get('/api/accesos/')
        self.assertEqual(len(resp.data), 1)
        self.assertEqual(resp.data[0]['sucursal'], self.norte.id)

    def test_pagos_acotados_via_membresia(self):
        _, m_c = self.socio_en(self.centro, 'AnaCentro')
        _, m_n = self.socio_en(self.norte, 'BetoNorte')
        Pago.objects.create(membresia=m_c, monto=Decimal('500'), metodo='efectivo')
        Pago.objects.create(membresia=m_n, monto=Decimal('300'), metodo='efectivo')

        self.assertEqual(len(self.client.get('/api/socios/pagos/').data), 2)
        self.authenticate(self.recep_centro)
        resp = self.client.get('/api/socios/pagos/')
        self.assertEqual(len(resp.data), 1)
        self.assertEqual(Decimal(resp.data[0]['monto']), Decimal('500'))

    def test_ventas_y_resumen_acotados(self):
        crear_producto(self.gym, self.centro, 'Agua', 20, stock=100, costo=8)
        for suc, metodo in ((self.centro, 'efectivo'), (self.norte, 'tarjeta')):
            Venta.objects.create(gym=self.gym, sucursal=suc, total=Decimal('20'), metodo=metodo)

        self.assertEqual(len(self.client.get('/api/tienda/ventas/').data), 2)
        self.assertEqual(
            Decimal(self.client.get('/api/tienda/ventas/resumen/').data['total_ventas']),
            Decimal('40'),
        )
        self.authenticate(self.recep_norte)
        self.assertEqual(len(self.client.get('/api/tienda/ventas/').data), 1)
        self.assertEqual(
            Decimal(self.client.get('/api/tienda/ventas/resumen/').data['total_ventas']),
            Decimal('20'),
        )

    def test_stats_acotadas(self):
        socio_c, m_c = self.socio_en(self.centro, 'AnaCentro')
        socio_n, m_n = self.socio_en(self.norte, 'BetoNorte')
        Acceso.objects.create(socio=socio_c, sucursal=self.centro, membresia=m_c, resultado='permitido')
        for _ in range(3):
            Acceso.objects.create(socio=socio_n, sucursal=self.norte, membresia=m_n, resultado='permitido')

        self.assertEqual(self.client.get('/api/accesos/stats/').data['accesos_hoy'], 4)
        self.authenticate(self.recep_norte)
        self.assertEqual(self.client.get('/api/accesos/stats/').data['accesos_hoy'], 3)


class AlcanceEscrituraTests(BaseDosSucursales):
    """Filtrar la lectura no basta: hay que bloquear el POST a la sucursal ajena."""

    def test_no_puede_crear_membresia_en_otra_sucursal(self):
        socio = Socio.objects.create(gym=self.gym, sucursal=self.norte, nombre='X', apellido='Y')
        self.authenticate(self.recep_norte)
        resp = self.client.post('/api/socios/membresias/', {
            'socio': socio.id, 'plan': self.plan.id, 'sucursal': self.centro.id,
            'fecha_inicio': str(date.today()), 'fecha_fin': str(date.today() + timedelta(days=30)),
            'estado': 'activa',
        })
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Membresia.objects.filter(sucursal=self.centro).count(), 0)

    def test_no_puede_cobrar_membresia_de_otra_sucursal(self):
        _, membresia = self.socio_en(self.centro, 'AnaCentro')
        self.authenticate(self.recep_norte)
        resp = self.client.post('/api/socios/pagos/', {
            'membresia': membresia.id, 'monto': '500', 'metodo': 'efectivo',
        })
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Pago.objects.count(), 0)

    def test_no_puede_vender_en_otra_sucursal(self):
        producto = crear_producto(self.gym, self.centro, 'Agua', 20, stock=10)
        self.authenticate(self.recep_norte)
        resp = self.client.post('/api/tienda/ventas/', {
            'sucursal': self.centro.id, 'metodo': 'efectivo',
            'items': [{'producto': producto.id, 'cantidad': 1}],
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Venta.objects.count(), 0)
        self.assertEqual(producto.stock_en(self.centro.id), 10)

    def test_no_puede_registrar_acceso_en_otra_sucursal(self):
        self.socio_en(self.norte, 'BetoNorte')
        self.authenticate(self.recep_norte)
        resp = self.client.post('/api/accesos/checkin/', {
            'token': 'QR-BetoNorte', 'sucursal_id': self.centro.id,
        })
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Acceso.objects.count(), 0)

    def test_duenio_si_puede_escribir_en_ambas(self):
        producto = crear_producto(self.gym, self.centro, 'Agua', 20, stock=10)
        StockSucursal.objects.create(producto=producto, sucursal=self.norte, cantidad=10)
        for suc in (self.centro, self.norte):
            resp = self.client.post('/api/tienda/ventas/', {
                'sucursal': suc.id, 'metodo': 'efectivo',
                'items': [{'producto': producto.id, 'cantidad': 1}],
            }, format='json')
            self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)

    def test_socio_nuevo_hereda_la_sucursal_de_quien_lo_registra(self):
        self.authenticate(self.recep_norte)
        resp = self.client.post('/api/socios/', {'nombre': 'Nuevo', 'apellido': 'Socio'})
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        self.assertEqual(Socio.objects.get(id=resp.data['id']).sucursal_id, self.norte.id)

    def test_usuario_no_puede_apuntar_a_sucursal_de_otro_gym(self):
        ajena = Sucursal.objects.create(gym=self.otro_gym, nombre='Ajena')
        resp = self.client.post('/api/usuarios/', {
            'email': 'x@round3.com', 'nombre': 'X', 'rol': 'recepcion',
            'gym': self.gym.id, 'sucursal': ajena.id, 'password': 'Passw0rd1',
        })
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)


class PoliticaVisitantesTests(BaseDosSucursales):
    def setUp(self):
        super().setUp()
        self.socio_centro, _ = self.socio_en(self.centro, 'AnaCentro')
        self.authenticate(self.recep_norte)

    def checkin(self, **extra):
        cache.clear()
        body = {'token': 'QR-AnaCentro', 'sucursal_id': self.norte.id}
        body.update(extra)
        return self.client.post('/api/accesos/checkin/', body)

    def test_libre_deja_entrar_al_visitante(self):
        self.gym.politica_visitantes = 'libre'
        self.gym.save()
        resp = self.checkin()
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.assertEqual(resp.data['acceso'], 'permitido')
        self.assertTrue(resp.data['visitante'])
        self.assertEqual(resp.data['sucursal_socio'], 'Centro')

    def test_bloqueado_niega_aunque_traiga_password(self):
        self.gym.politica_visitantes = 'bloqueado'
        self.gym.save()
        resp = self.checkin(password='Passw0rd1')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(resp.data['motivo'], 'pertenece a otra sucursal')
        self.assertFalse(resp.data['requiere_autorizacion'])
        acceso = Acceso.objects.get()
        self.assertEqual(acceso.resultado, 'denegado')
        self.assertEqual(acceso.motivo_denegado, 'otra_sucursal')

    def test_autorizacion_niega_de_entrada_pero_ofrece_el_override(self):
        """Sin pulsar 'Autorizar' la puerta sigue cerrada: la política no es 'libre'."""
        self.gym.politica_visitantes = 'autorizacion'
        self.gym.save()
        resp = self.checkin()
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(resp.data['requiere_autorizacion'])
        self.assertEqual(resp.data['sucursal_socio'], 'Centro')

    def test_autorizar_deja_entrar_y_registra_quien_lo_hizo(self):
        """Un clic basta: no se pide contraseña.

        El respaldo pasa a ser la bitácora, así que lo que importa es que el acceso
        quede firmado por quien estaba en el mostrador. Si `autorizado_por` se
        guardara nulo, la política sería indistinguible de 'libre'.
        """
        self.gym.politica_visitantes = 'autorizacion'
        self.gym.save()
        resp = self.checkin(autorizar=True)
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.assertEqual(resp.data['autorizado_por'], self.recep_norte.nombre)
        acceso = Acceso.objects.get(resultado='permitido')
        self.assertEqual(acceso.autorizado_por_id, self.recep_norte.id)

    def test_bloqueado_no_se_puede_forzar_con_autorizar(self):
        """'Solo su sucursal' significa que no hay override que valga."""
        self.gym.politica_visitantes = 'bloqueado'
        self.gym.save()
        resp = self.checkin(autorizar=True)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(resp.data['requiere_autorizacion'])
        self.assertEqual(
            Acceso.objects.get(resultado='denegado').motivo_denegado, 'otra_sucursal',
        )

    def test_password_ya_no_autoriza_visita(self):
        """Queda como guardia: el camino viejo por contraseña no debe seguir vivo."""
        self.gym.politica_visitantes = 'autorizacion'
        self.gym.save()
        resp = self.checkin(password='Passw0rd1')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_socio_de_su_propia_sucursal_no_pide_nada(self):
        self.gym.politica_visitantes = 'bloqueado'
        self.gym.save()
        self.socio_en(self.norte, 'BetoNorte')
        cache.clear()
        resp = self.client.post('/api/accesos/checkin/', {
            'token': 'QR-BetoNorte', 'sucursal_id': self.norte.id,
        })
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.assertFalse(resp.data['visitante'])

    def test_socio_sin_sucursal_entra_a_cualquiera(self):
        """NULL significa 'de ninguna en particular', no 'de ninguna'."""
        self.gym.politica_visitantes = 'bloqueado'
        self.gym.save()
        self.socio_centro.sucursal = None
        self.socio_centro.save()
        resp = self.checkin()
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)

    def test_membresia_vencida_gana_a_la_politica(self):
        """Primero se revisa que pague; ser de la casa no lo salva."""
        self.gym.politica_visitantes = 'libre'
        self.gym.save()
        Membresia.objects.filter(socio=self.socio_centro).update(estado='vencida')
        resp = self.checkin()
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(Acceso.objects.get().motivo_denegado, 'membresia_vencida')


class TokenTests(BaseDosSucursales):
    def test_jwt_lleva_la_sucursal(self):
        from django.urls import reverse
        import base64, json

        cache.clear()
        resp = self.client.post(reverse('token_obtain'), {
            'email': 'norte@round3.com', 'password': 'Passw0rd1',
        })
        payload = resp.data['access'].split('.')[1]
        payload += '=' * (-len(payload) % 4)
        datos = json.loads(base64.urlsafe_b64decode(payload))
        self.assertEqual(datos['sucursal_id'], self.norte.id)
        self.assertEqual(datos['sucursal_nombre'], 'Norte')

    def test_jwt_del_duenio_no_lleva_sucursal(self):
        from django.urls import reverse
        import base64, json

        cache.clear()
        resp = self.client.post(reverse('token_obtain'), {
            'email': 'admin@round3.com', 'password': 'Passw0rd1',
        })
        payload = resp.data['access'].split('.')[1]
        payload += '=' * (-len(payload) % 4)
        datos = json.loads(base64.urlsafe_b64decode(payload))
        self.assertIsNone(datos['sucursal_id'])
        self.assertIsNone(datos['sucursal_nombre'])
