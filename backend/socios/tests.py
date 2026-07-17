from datetime import date, timedelta

from rest_framework import status

from gyms.tests import BaseAPITestCase
from socios.models import Plan, Socio, Membresia, Pago


class SocioCRUDTests(BaseAPITestCase):
    def test_create_socio(self):
        resp = self.client.post('/api/socios/', {
            'nombre': 'Juan', 'apellido': 'Perez', 'email': 'juan@test.com',
        })
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        self.assertEqual(Socio.objects.count(), 1)
        self.assertEqual(Socio.objects.first().gym_id, self.gym.id)

    def test_list_socios_scoped_to_gym(self):
        Socio.objects.create(gym=self.gym, nombre='Ana', apellido='Lopez')
        Socio.objects.create(gym=self.otro_gym, nombre='Pedro', apellido='Ajeno')
        resp = self.client.get('/api/socios/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        nombres = [s['nombre'] for s in resp.data]
        self.assertIn('Ana', nombres)
        self.assertNotIn('Pedro', nombres)

    def test_update_socio(self):
        socio = Socio.objects.create(gym=self.gym, nombre='Ana', apellido='Lopez')
        resp = self.client.patch(f'/api/socios/{socio.id}/', {'telefono': '5512345678'})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        socio.refresh_from_db()
        self.assertEqual(socio.telefono, '5512345678')

    def test_cannot_access_socio_from_other_gym(self):
        ajeno = Socio.objects.create(gym=self.otro_gym, nombre='Pedro', apellido='Ajeno')
        resp = self.client.get(f'/api/socios/{ajeno.id}/')
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_membresia_activa_field(self):
        socio = Socio.objects.create(gym=self.gym, nombre='Ana', apellido='Lopez')
        plan = Plan.objects.create(gym=self.gym, nombre='Mensual', tipo='mensual', precio=500)
        Membresia.objects.create(
            socio=socio, plan=plan, sucursal=self.sucursal,
            fecha_inicio=date.today(), fecha_fin=date.today() + timedelta(days=30),
            estado='activa',
        )
        resp = self.client.get(f'/api/socios/{socio.id}/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIsNotNone(resp.data['membresia_activa'])
        self.assertEqual(resp.data['membresia_activa']['plan'], 'Mensual')


class MembresiaTests(BaseAPITestCase):
    def setUp(self):
        super().setUp()
        self.socio = Socio.objects.create(gym=self.gym, nombre='Ana', apellido='Lopez')
        self.plan = Plan.objects.create(gym=self.gym, nombre='Mensual', tipo='mensual', precio=500, duracion_dias=30)

    def test_create_membresia(self):
        resp = self.client.post('/api/socios/membresias/', {
            'socio': self.socio.id, 'plan': self.plan.id, 'sucursal': self.sucursal.id,
            'fecha_inicio': date.today().isoformat(), 'estado': 'activa',
        })
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)

    def test_list_membresias_scoped(self):
        Membresia.objects.create(
            socio=self.socio, plan=self.plan, sucursal=self.sucursal,
            fecha_inicio=date.today(), estado='activa',
        )
        resp = self.client.get('/api/socios/membresias/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data), 1)


class PagoTests(BaseAPITestCase):
    def setUp(self):
        super().setUp()
        self.socio = Socio.objects.create(gym=self.gym, nombre='Ana', apellido='Lopez')
        self.plan = Plan.objects.create(gym=self.gym, nombre='Mensual', tipo='mensual', precio=500)
        self.membresia = Membresia.objects.create(
            socio=self.socio, plan=self.plan, sucursal=self.sucursal,
            fecha_inicio=date.today(), estado='activa',
        )

    def test_create_pago_sets_registrado_por(self):
        resp = self.client.post('/api/socios/pagos/', {
            'membresia': self.membresia.id, 'monto': '500.00', 'metodo': 'efectivo',
        })
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        pago = Pago.objects.get(id=resp.data['id'])
        self.assertEqual(pago.registrado_por, self.user)
