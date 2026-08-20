from datetime import date, timedelta

from django.core.cache import cache
from rest_framework import status

from gyms.models import Gym, Sucursal
from gyms.tests import BaseAPITestCase
from socios.models import AjusteMembresia, Membresia, Plan, Socio
from usuarios.models import Usuario


class AjusteVencimientoTests(BaseAPITestCase):
    def setUp(self):
        super().setUp()
        self.plan = Plan.objects.create(
            gym=self.gym, nombre='Mensual', tipo='mensual', precio=500, duracion_dias=30,
        )
        self.socio = Socio.objects.create(gym=self.gym, nombre='Ana', apellido='Lopez')
        self.membresia = Membresia.objects.create(
            socio=self.socio, plan=self.plan, sucursal=self.sucursal,
            fecha_inicio=date.today() - timedelta(days=40),
            fecha_fin=date.today() - timedelta(days=10),
            estado='vencida',
        )
        self.recepcion = Usuario.objects.create_user(
            email='caja@round3.com', password='Recepcion1', nombre='Caja',
            rol='recepcion', gym=self.gym,
        )

    def url(self, membresia=None):
        return f'/api/socios/membresias/{(membresia or self.membresia).id}/ajustar-vencimiento/'

    def ajustar(self, password='Passw0rd1', dias=20, **extra):
        cache.clear()   # el throttle de 5/min vive en caché entre llamadas
        body = {'fecha_fin': str(date.today() + timedelta(days=dias)), 'password': password}
        body.update(extra)
        return self.client.post(self.url(), body)

    # --- camino feliz ---

    def test_admin_ajusta_con_su_password(self):
        resp = self.ajustar()
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.membresia.refresh_from_db()
        self.assertEqual(self.membresia.fecha_fin, date.today() + timedelta(days=20))

    def test_extender_al_futuro_reactiva_la_membresia(self):
        self.ajustar(dias=20)
        self.membresia.refresh_from_db()
        self.assertEqual(self.membresia.estado, 'activa')
        # y ahora sí deja pasar por la puerta
        self.assertTrue(Membresia.objects.vigentes().filter(id=self.membresia.id).exists())

    def test_fecha_al_pasado_marca_vencida(self):
        self.membresia.estado = 'activa'
        self.membresia.fecha_fin = date.today() + timedelta(days=30)
        self.membresia.save()
        self.ajustar(dias=-5)
        self.membresia.refresh_from_db()
        self.assertEqual(self.membresia.estado, 'vencida')
        self.assertFalse(Membresia.objects.vigentes().filter(id=self.membresia.id).exists())

    def test_suspendida_no_se_reactiva_sola(self):
        self.membresia.estado = 'suspendida'
        self.membresia.save()
        self.ajustar(dias=20)
        self.membresia.refresh_from_db()
        self.assertEqual(self.membresia.estado, 'suspendida')

    def test_pendiente_pago_no_se_reactiva_sola(self):
        self.membresia.estado = 'pendiente_pago'
        self.membresia.save()
        self.ajustar(dias=20)
        self.membresia.refresh_from_db()
        self.assertEqual(self.membresia.estado, 'pendiente_pago')

    # --- autorización ---

    def test_password_incorrecta_rechaza_y_no_cambia_nada(self):
        original = self.membresia.fecha_fin
        resp = self.ajustar(password='no-es-esta')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self.membresia.refresh_from_db()
        self.assertEqual(self.membresia.fecha_fin, original)
        self.assertEqual(AjusteMembresia.objects.count(), 0)

    def test_password_vacia_rechaza(self):
        resp = self.ajustar(password='')
        self.assertIn(resp.status_code, (status.HTTP_400_BAD_REQUEST, status.HTTP_403_FORBIDDEN))
        self.assertEqual(AjusteMembresia.objects.count(), 0)

    def test_sin_password_es_400(self):
        cache.clear()
        resp = self.client.post(self.url(), {'fecha_fin': str(date.today())})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_recepcion_puede_ajustar_con_password_del_dueno(self):
        """El caso real: recepción tiene la pantalla, el dueño teclea su contraseña."""
        self.authenticate(self.recepcion, password='Recepcion1')
        resp = self.ajustar(password='Passw0rd1')
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        ajuste = AjusteMembresia.objects.get()
        self.assertEqual(ajuste.solicitado_por_id, self.recepcion.id)
        self.assertEqual(ajuste.autorizado_por_id, self.user.id)

    def test_password_de_recepcion_no_autoriza(self):
        self.authenticate(self.recepcion, password='Recepcion1')
        resp = self.ajustar(password='Recepcion1')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_password_de_admin_de_otro_gym_no_autoriza(self):
        Usuario.objects.create_user(
            email='ajeno@otro.com', password='Ajeno12345', nombre='Ajeno',
            rol='admin', gym=self.otro_gym,
        )
        resp = self.ajustar(password='Ajeno12345')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_inactivo_no_autoriza(self):
        self.user.is_active = False
        self.user.save()
        # el token sigue siendo válido, pero su contraseña ya no debe autorizar
        resp = self.ajustar(password='Passw0rd1')
        self.assertIn(resp.status_code, (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN))

    def test_requiere_autenticacion(self):
        cache.clear()
        self.client.credentials()
        resp = self.client.post(self.url(), {
            'fecha_fin': str(date.today()), 'password': 'Passw0rd1',
        })
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    # --- aislamiento multitenant ---

    def test_membresia_de_otro_gym_da_404(self):
        otro_plan = Plan.objects.create(
            gym=self.otro_gym, nombre='X', tipo='mensual', precio=1, duracion_dias=30,
        )
        otro_socio = Socio.objects.create(gym=self.otro_gym, nombre='Pedro', apellido='Ajeno')
        otra_sucursal = Sucursal.objects.create(gym=self.otro_gym, nombre='Ajena')
        ajena = Membresia.objects.create(
            socio=otro_socio, plan=otro_plan, sucursal=otra_sucursal,
            fecha_inicio=date.today(), fecha_fin=date.today(), estado='activa',
        )
        cache.clear()
        resp = self.client.post(self.url(ajena), {
            'fecha_fin': str(date.today() + timedelta(days=365)), 'password': 'Passw0rd1',
        })
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
        ajena.refresh_from_db()
        self.assertEqual(ajena.fecha_fin, date.today())

    # --- validación de datos ---

    def test_fecha_anterior_al_inicio_rechazada(self):
        cache.clear()
        resp = self.client.post(self.url(), {
            'fecha_fin': str(self.membresia.fecha_inicio - timedelta(days=1)),
            'password': 'Passw0rd1',
        })
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_fecha_invalida_rechazada(self):
        cache.clear()
        resp = self.client.post(self.url(), {'fecha_fin': 'mañana', 'password': 'Passw0rd1'})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    # --- bitácora ---

    def test_ajuste_queda_registrado_con_datos_completos(self):
        anterior = self.membresia.fecha_fin
        self.ajustar(dias=20, motivo='Cliente pagó en efectivo el viernes')
        ajuste = AjusteMembresia.objects.get()
        self.assertEqual(ajuste.membresia_id, self.membresia.id)
        self.assertEqual(ajuste.fecha_anterior, anterior)
        self.assertEqual(ajuste.fecha_nueva, date.today() + timedelta(days=20))
        self.assertEqual(ajuste.estado_anterior, 'vencida')
        self.assertEqual(ajuste.estado_nuevo, 'activa')
        self.assertEqual(ajuste.motivo, 'Cliente pagó en efectivo el viernes')
        self.assertEqual(ajuste.solicitado_por_id, self.user.id)
        self.assertEqual(ajuste.autorizado_por_id, self.user.id)

    def test_la_password_no_se_devuelve_en_la_respuesta(self):
        resp = self.ajustar()
        self.assertNotIn('password', str(resp.data))
        self.assertNotIn('Passw0rd1', str(resp.data))

    def test_endpoint_de_bitacora(self):
        self.ajustar(dias=10, motivo='primero')
        self.ajustar(dias=20, motivo='segundo')
        cache.clear()
        resp = self.client.get(f'/api/socios/membresias/{self.membresia.id}/ajustes/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data), 2)
        self.assertEqual(resp.data[0]['autorizado_por_nombre'], 'Admin')

    def test_bitacora_de_otro_gym_da_404(self):
        otro_plan = Plan.objects.create(
            gym=self.otro_gym, nombre='X', tipo='mensual', precio=1, duracion_dias=30,
        )
        otro_socio = Socio.objects.create(gym=self.otro_gym, nombre='Pedro', apellido='Ajeno')
        otra_sucursal = Sucursal.objects.create(gym=self.otro_gym, nombre='Ajena')
        ajena = Membresia.objects.create(
            socio=otro_socio, plan=otro_plan, sucursal=otra_sucursal,
            fecha_inicio=date.today(), fecha_fin=date.today(), estado='activa',
        )
        resp = self.client.get(f'/api/socios/membresias/{ajena.id}/ajustes/')
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    # --- rate limit ---

    def test_intentos_fallidos_se_limitan(self):
        cache.clear()
        codigos = []
        for _ in range(8):
            resp = self.client.post(self.url(), {
                'fecha_fin': str(date.today()), 'password': f'malo',
            })
            codigos.append(resp.status_code)
        self.assertIn(status.HTTP_429_TOO_MANY_REQUESTS, codigos)
        cache.clear()


class MembresiaRecienteTests(BaseAPITestCase):
    def test_socio_vencido_expone_membresia_reciente(self):
        """membresia_activa es null para un vencido; la UI necesita igual su fecha."""
        plan = Plan.objects.create(
            gym=self.gym, nombre='Mensual', tipo='mensual', precio=500, duracion_dias=30,
        )
        socio = Socio.objects.create(gym=self.gym, nombre='Ana', apellido='Lopez')
        Membresia.objects.create(
            socio=socio, plan=plan, sucursal=self.sucursal,
            fecha_inicio=date.today() - timedelta(days=40),
            fecha_fin=date.today() - timedelta(days=10),
            estado='vencida',
        )
        resp = self.client.get(f'/api/socios/{socio.id}/')
        self.assertIsNone(resp.data['membresia_activa'])
        self.assertIsNotNone(resp.data['membresia_reciente'])
        self.assertEqual(resp.data['membresia_reciente']['estado'], 'vencida')

    def test_socio_sin_membresias(self):
        socio = Socio.objects.create(gym=self.gym, nombre='Nuevo', apellido='Socio')
        resp = self.client.get(f'/api/socios/{socio.id}/')
        self.assertIsNone(resp.data['membresia_reciente'])
