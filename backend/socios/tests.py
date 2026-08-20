from datetime import date, timedelta

from rest_framework import status

from gyms.tests import BaseAPITestCase
from socios.models import Plan, Socio, Membresia, Pago, Gasto
from usuarios.models import Usuario


class SocioCRUDTests(BaseAPITestCase):
    def test_create_socio(self):
        resp = self.client.post('/api/socios/', {
            'nombre': 'Juan', 'apellido': 'Perez', 'email': 'juan@test.com',
        })
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        self.assertEqual(Socio.objects.count(), 1)
        self.assertEqual(Socio.objects.first().gym_id, self.gym.id)

    def test_create_socio_genera_codigo_qr(self):
        resp = self.client.post('/api/socios/', {'nombre': 'Juan', 'apellido': 'Perez'})
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        socio = Socio.objects.get(id=resp.data['id'])
        metodo = socio.metodos_acceso.filter(tipo='qr', activo=True).first()
        self.assertIsNotNone(metodo)
        self.assertTrue(metodo.token.startswith('R3B-QR-'))

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


class NumeroSocioTests(BaseAPITestCase):
    """Número de socio: consecutivo por gym desde 1000, distinto del token del QR.

    Es lo que recepción dice en voz alta y busca a mano; el QR sigue siendo el
    código con parte aleatoria (`R3B-QR-...`), porque ese abre la puerta y un
    consecutivo ahí se adivina probando números seguidos.
    """

    def test_primer_socio_del_gym_empieza_en_1000(self):
        resp = self.client.post('/api/socios/', {'nombre': 'Juan', 'apellido': 'Perez'})
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        self.assertEqual(resp.data['numero_socio'], 1000)

    def test_numeros_consecutivos_dentro_del_mismo_gym(self):
        primero = self.client.post('/api/socios/', {'nombre': 'A', 'apellido': 'A'})
        segundo = self.client.post('/api/socios/', {'nombre': 'B', 'apellido': 'B'})
        tercero = self.client.post('/api/socios/', {'nombre': 'C', 'apellido': 'C'})
        self.assertEqual(
            [primero.data['numero_socio'], segundo.data['numero_socio'], tercero.data['numero_socio']],
            [1000, 1001, 1002],
        )

    def test_numero_socio_no_es_el_codigo_del_qr(self):
        resp = self.client.post('/api/socios/', {'nombre': 'Juan', 'apellido': 'Perez'})
        self.assertNotEqual(str(resp.data['numero_socio']), resp.data['codigo_acceso'])
        self.assertTrue(resp.data['codigo_acceso'].startswith('R3B-QR-'))

    def test_cada_gym_numera_desde_1000_por_su_cuenta(self):
        """Dos negocios no comparten la numeración: cada uno ve su propia lista
        empezar en 1000, no un consecutivo global del sistema completo."""
        propio = self.client.post('/api/socios/', {'nombre': 'Propio', 'apellido': 'X'})
        self.assertEqual(propio.data['numero_socio'], 1000)

        admin_ajeno = Usuario.objects.create_user(
            email='admin@otro.com', password='Passw0rd1', nombre='Otro Admin',
            rol='admin', gym=self.otro_gym,
        )
        self.authenticate(admin_ajeno)
        ajeno = self.client.post('/api/socios/', {'nombre': 'Ajeno', 'apellido': 'X'})
        self.assertEqual(ajeno.data['numero_socio'], 1000)

    def test_cliente_no_puede_fijar_su_propio_numero_de_socio(self):
        """numero_socio es read_only: el body lo ignora, el servidor manda."""
        resp = self.client.post('/api/socios/', {
            'nombre': 'Juan', 'apellido': 'Perez', 'numero_socio': 9999,
        })
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        self.assertEqual(resp.data['numero_socio'], 1000)

    def test_alta_no_exige_gym_en_el_body(self):
        """El UniqueConstraint(gym, numero_socio) no debe forzar a mandar 'gym': lo
        pone el servidor desde el usuario autenticado, como siempre. Regresión de
        un efecto colateral conocido de DRF con unique_together/UniqueConstraint."""
        resp = self.client.post('/api/socios/', {'nombre': 'Juan', 'apellido': 'Perez'})
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)

    def test_dar_de_baja_y_alta_no_reutiliza_numero(self):
        """Cancelar los datos de un socio (ARCO) no libera su número para que otro
        lo tome: sería confuso que dos personas distintas hayan sido alguna vez
        el 'socio 1000'."""
        primero = self.client.post('/api/socios/', {'nombre': 'A', 'apellido': 'A'})
        self.client.post(
            f"/api/socios/{primero.data['id']}/cancelar-datos/", {'password': 'Passw0rd1'},
        )
        segundo = self.client.post('/api/socios/', {'nombre': 'B', 'apellido': 'B'})
        self.assertEqual(segundo.data['numero_socio'], 1001)


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

    def test_list_pagos_scoped_to_gym(self):
        Pago.objects.create(membresia=self.membresia, monto=500, metodo='efectivo')
        resp = self.client.get('/api/socios/pagos/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data), 1)


class PlanTests(BaseAPITestCase):
    def test_create_plan(self):
        resp = self.client.post('/api/socios/planes/', {
            'gym': self.gym.id, 'nombre': 'Anual', 'tipo': 'anual',
            'precio': '4500.00', 'duracion_dias': 365,
        })
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        self.assertTrue(Plan.objects.filter(nombre='Anual', gym=self.gym).exists())

    def test_list_planes_scoped_to_gym(self):
        Plan.objects.create(gym=self.gym, nombre='Mensual', tipo='mensual', precio=500)
        Plan.objects.create(gym=self.otro_gym, nombre='Ajeno', tipo='mensual', precio=100)
        resp = self.client.get('/api/socios/planes/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        nombres = [p['nombre'] for p in resp.data]
        self.assertIn('Mensual', nombres)
        self.assertNotIn('Ajeno', nombres)

    def test_recepcion_no_puede_crear_plan(self):
        recepcion = Usuario.objects.create_user(
            email='recep@round3.com', password='Passw0rd1', nombre='Recep',
            rol='recepcion', gym=self.gym,
        )
        self.authenticate(recepcion)
        resp = self.client.post('/api/socios/planes/', {
            'gym': self.gym.id, 'nombre': 'Hack', 'tipo': 'mensual', 'precio': '1.00',
        })
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_recepcion_si_puede_leer_planes(self):
        Plan.objects.create(gym=self.gym, nombre='Mensual', tipo='mensual', precio=500)
        recepcion = Usuario.objects.create_user(
            email='recep@round3.com', password='Passw0rd1', nombre='Recep',
            rol='recepcion', gym=self.gym,
        )
        self.authenticate(recepcion)
        resp = self.client.get('/api/socios/planes/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data), 1)


class GastoTests(BaseAPITestCase):
    def test_create_gasto_sets_gym_y_registrado_por(self):
        resp = self.client.post('/api/socios/gastos/', {
            'categoria': 'renta', 'descripcion': 'Renta julio',
            'monto': '8000.00', 'fecha': date.today().isoformat(),
        })
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        gasto = Gasto.objects.get(id=resp.data['id'])
        self.assertEqual(gasto.gym_id, self.gym.id)
        self.assertEqual(gasto.registrado_por, self.user)

    def test_list_gastos_scoped_to_gym(self):
        Gasto.objects.create(gym=self.gym, categoria='renta', descripcion='Mia', monto=100, fecha=date.today())
        Gasto.objects.create(gym=self.otro_gym, categoria='renta', descripcion='Ajena', monto=100, fecha=date.today())
        resp = self.client.get('/api/socios/gastos/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        descripciones = [g['descripcion'] for g in resp.data]
        self.assertIn('Mia', descripciones)
        self.assertNotIn('Ajena', descripciones)

    def test_recepcion_no_accede_gastos(self):
        recepcion = Usuario.objects.create_user(
            email='recep@round3.com', password='Passw0rd1', nombre='Recep',
            rol='recepcion', gym=self.gym,
        )
        self.authenticate(recepcion)
        resp = self.client.get('/api/socios/gastos/')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_delete_gasto(self):
        gasto = Gasto.objects.create(gym=self.gym, categoria='otro', descripcion='X', monto=50, fecha=date.today())
        resp = self.client.delete(f'/api/socios/gastos/{gasto.id}/')
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Gasto.objects.filter(id=gasto.id).exists())
