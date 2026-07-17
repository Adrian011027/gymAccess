from datetime import date, timedelta

from rest_framework import status

from gyms.tests import BaseAPITestCase
from socios.models import Plan, Socio, Membresia
from accesos.models import Acceso, MetodoAcceso


class CheckInTests(BaseAPITestCase):
    def setUp(self):
        super().setUp()
        self.socio = Socio.objects.create(gym=self.gym, nombre='Ana', apellido='Lopez')
        self.plan = Plan.objects.create(gym=self.gym, nombre='Mensual', tipo='mensual', precio=500)
        self.metodo = MetodoAcceso.objects.create(socio=self.socio, tipo='qr', token='TOKEN123')

    def test_checkin_denegado_sin_membresia(self):
        resp = self.client.post('/api/accesos/checkin/', {
            'token': 'TOKEN123', 'sucursal_id': self.sucursal.id,
        })
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        acceso = Acceso.objects.get(socio=self.socio)
        self.assertEqual(acceso.resultado, 'denegado')
        self.assertEqual(acceso.motivo_denegado, 'sin_membresia')

    def test_checkin_denegado_membresia_vencida(self):
        Membresia.objects.create(
            socio=self.socio, plan=self.plan, sucursal=self.sucursal,
            fecha_inicio=date.today() - timedelta(days=60),
            fecha_fin=date.today() - timedelta(days=1), estado='vencida',
        )
        resp = self.client.post('/api/accesos/checkin/', {
            'token': 'TOKEN123', 'sucursal_id': self.sucursal.id,
        })
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        acceso = Acceso.objects.get(socio=self.socio)
        self.assertEqual(acceso.motivo_denegado, 'membresia_vencida')

    def test_checkin_permitido(self):
        Membresia.objects.create(
            socio=self.socio, plan=self.plan, sucursal=self.sucursal,
            fecha_inicio=date.today(), fecha_fin=date.today() + timedelta(days=30),
            estado='activa',
        )
        resp = self.client.post('/api/accesos/checkin/', {
            'token': 'TOKEN123', 'sucursal_id': self.sucursal.id,
        })
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['acceso'], 'permitido')
        acceso = Acceso.objects.get(socio=self.socio)
        self.assertEqual(acceso.resultado, 'permitido')

    def test_checkin_token_invalido(self):
        resp = self.client.post('/api/accesos/checkin/', {
            'token': 'NOEXISTE', 'sucursal_id': self.sucursal.id,
        })
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_checkin_metodo_inactivo(self):
        self.metodo.activo = False
        self.metodo.save()
        resp = self.client.post('/api/accesos/checkin/', {
            'token': 'TOKEN123', 'sucursal_id': self.sucursal.id,
        })
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_checkin_huella_permitido(self):
        huella = MetodoAcceso.objects.create(socio=self.socio, tipo='huella', token='FP-HASH-ABC')
        Membresia.objects.create(
            socio=self.socio, plan=self.plan, sucursal=self.sucursal,
            fecha_inicio=date.today(), fecha_fin=date.today() + timedelta(days=30),
            estado='activa',
        )
        resp = self.client.post('/api/accesos/checkin/', {
            'token': huella.token, 'sucursal_id': self.sucursal.id,
        })
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        acceso = Acceso.objects.get(socio=self.socio)
        self.assertEqual(acceso.metodo_usado, 'huella')


class MetodoAccesoTests(BaseAPITestCase):
    def setUp(self):
        super().setUp()
        self.socio = Socio.objects.create(gym=self.gym, nombre='Ana', apellido='Lopez')

    def test_registrar_metodo_huella(self):
        resp = self.client.post('/api/accesos/metodos/', {
            'socio': self.socio.id, 'tipo': 'huella', 'token': 'FP-HASH-XYZ',
        })
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        self.assertEqual(MetodoAcceso.objects.filter(socio=self.socio, tipo='huella').count(), 1)

    def test_token_unico(self):
        MetodoAcceso.objects.create(socio=self.socio, tipo='qr', token='DUP')
        resp = self.client.post('/api/accesos/metodos/', {
            'socio': self.socio.id, 'tipo': 'huella', 'token': 'DUP',
        })
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_list_metodos_scoped_to_gym(self):
        otro_socio = Socio.objects.create(gym=self.otro_gym, nombre='Pedro', apellido='Ajeno')
        MetodoAcceso.objects.create(socio=otro_socio, tipo='qr', token='AJENO')
        MetodoAcceso.objects.create(socio=self.socio, tipo='qr', token='MIO')
        resp = self.client.get('/api/accesos/metodos/')
        tokens = [m['token'] for m in resp.data]
        self.assertIn('MIO', tokens)
        self.assertNotIn('AJENO', tokens)


class SincronizarHuellaTests(BaseAPITestCase):
    def setUp(self):
        super().setUp()
        self.socio = Socio.objects.create(gym=self.gym, nombre='Ana', apellido='Lopez')

    def test_sincronizar_huella_ok(self):
        resp = self.client.post('/api/accesos/sincronizar-huella/', {
            'socio_id': self.socio.id, 'template': 'FP-TEMPLATE-1',
        })
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.assertTrue(MetodoAcceso.objects.filter(socio=self.socio, tipo='huella', token='FP-TEMPLATE-1').exists())

    def test_sincronizar_huella_reemplaza_anterior(self):
        MetodoAcceso.objects.create(socio=self.socio, tipo='huella', token='OLD')
        resp = self.client.post('/api/accesos/sincronizar-huella/', {
            'socio_id': self.socio.id, 'template': 'NEW-TEMPLATE',
        })
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(MetodoAcceso.objects.filter(socio=self.socio, tipo='huella').count(), 1)
        self.assertEqual(MetodoAcceso.objects.get(socio=self.socio, tipo='huella').token, 'NEW-TEMPLATE')

    def test_sincronizar_huella_duplicada_en_otro_socio(self):
        otro = Socio.objects.create(gym=self.gym, nombre='Beto', apellido='Ruiz')
        MetodoAcceso.objects.create(socio=otro, tipo='huella', token='DUP-TEMPLATE')
        resp = self.client.post('/api/accesos/sincronizar-huella/', {
            'socio_id': self.socio.id, 'template': 'DUP-TEMPLATE',
        })
        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)

    def test_sincronizar_huella_socio_de_otro_gym(self):
        ajeno = Socio.objects.create(gym=self.otro_gym, nombre='Pedro', apellido='Ajeno')
        resp = self.client.post('/api/accesos/sincronizar-huella/', {
            'socio_id': ajeno.id, 'template': 'X',
        })
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_sincronizar_huella_faltan_campos(self):
        resp = self.client.post('/api/accesos/sincronizar-huella/', {'socio_id': self.socio.id})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)


class AccesoListStatsTests(BaseAPITestCase):
    def setUp(self):
        super().setUp()
        self.socio = Socio.objects.create(gym=self.gym, nombre='Ana', apellido='Lopez')

    def test_list_accesos_readonly(self):
        Acceso.objects.create(socio=self.socio, sucursal=self.sucursal, resultado='permitido', metodo_usado='qr')
        resp = self.client.get('/api/accesos/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data), 1)

    def test_accesos_readonly_no_post(self):
        resp = self.client.post('/api/accesos/', {'socio': self.socio.id, 'sucursal': self.sucursal.id, 'resultado': 'permitido'})
        self.assertEqual(resp.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_stats_endpoint(self):
        Acceso.objects.create(socio=self.socio, sucursal=self.sucursal, resultado='permitido', metodo_usado='qr')
        resp = self.client.get('/api/accesos/stats/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['accesos_hoy'], 1)
        self.assertIn('horarios_concurridos', resp.data)
