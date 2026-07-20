from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status

from gyms.models import Gym, Sucursal, Equipamiento
from usuarios.models import Usuario


class BaseAPITestCase(TestCase):
    """Base con gym + usuario autenticado, reusado en todos los apps."""

    def setUp(self):
        # Los contadores de throttling viven en la caché y sobreviven entre tests
        cache.clear()
        self.gym = Gym.objects.create(nombre='Round3 Boxing', tipo='box')
        self.otro_gym = Gym.objects.create(nombre='Otro Gym', tipo='mixto')
        self.sucursal = Sucursal.objects.create(gym=self.gym, nombre='Centro')

        self.user = Usuario.objects.create_user(
            email='admin@round3.com', password='Passw0rd1', nombre='Admin',
            rol='admin', gym=self.gym,
        )
        self.client = APIClient()
        self.authenticate(self.user)

    def authenticate(self, user, password='Passw0rd1'):
        resp = self.client.post(reverse('token_obtain'), {
            'email': user.email, 'password': password,
        })
        token = resp.data['access']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')


class AuthTests(BaseAPITestCase):
    def test_login_ok(self):
        client = APIClient()
        resp = client.post(reverse('token_obtain'), {
            'email': 'admin@round3.com', 'password': 'Passw0rd1',
        })
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn('access', resp.data)
        self.assertIn('refresh', resp.data)

    def test_login_bad_password(self):
        client = APIClient()
        resp = client.post(reverse('token_obtain'), {
            'email': 'admin@round3.com', 'password': 'wrong',
        })
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_endpoints_require_auth(self):
        client = APIClient()
        resp = client.get('/api/socios/')
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_refresh_token(self):
        client = APIClient()
        resp = client.post(reverse('token_obtain'), {
            'email': 'admin@round3.com', 'password': 'Passw0rd1',
        })
        refresh = resp.data['refresh']
        resp2 = client.post(reverse('token_refresh'), {'refresh': refresh})
        self.assertEqual(resp2.status_code, status.HTTP_200_OK)
        self.assertIn('access', resp2.data)


class ThrottleTests(BaseAPITestCase):
    """Rate limiting anti fuerza bruta / DoS a nivel aplicación."""

    def test_login_bloqueado_tras_intentos_excesivos(self):
        cache.clear()
        client = APIClient()
        for _ in range(10):
            resp = client.post(reverse('token_obtain'), {
                'email': 'admin@round3.com', 'password': 'wrong',
            })
            self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)
        # Intento 11 dentro del mismo minuto: bloqueado aunque la contraseña fuera correcta
        resp = client.post(reverse('token_obtain'), {
            'email': 'admin@round3.com', 'password': 'Passw0rd1',
        })
        self.assertEqual(resp.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertIn('Retry-After', resp.headers)

    def test_refresh_tambien_esta_limitado(self):
        cache.clear()
        client = APIClient()
        for _ in range(10):
            client.post(reverse('token_refresh'), {'refresh': 'basura'})
        resp = client.post(reverse('token_refresh'), {'refresh': 'basura'})
        self.assertEqual(resp.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

    def test_anonimo_nunca_toca_datos(self):
        # Sin autenticar, el 401 corta antes de tocar la base de datos
        client = APIClient()
        resp = client.get('/api/socios/')
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_usuario_flood_es_limitado(self):
        cache.clear()
        for _ in range(300):
            resp = self.client.get('/api/socios/')
            self.assertEqual(resp.status_code, status.HTTP_200_OK)
        # Petición 301 dentro del mismo minuto: bloqueada
        resp = self.client.get('/api/socios/')
        self.assertEqual(resp.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

    def test_uso_normal_no_es_bloqueado(self):
        for _ in range(5):
            resp = self.client.get('/api/socios/')
            self.assertEqual(resp.status_code, status.HTTP_200_OK)


class GymSucursalTests(BaseAPITestCase):
    def test_list_sucursales(self):
        resp = self.client.get('/api/gyms/sucursales/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        nombres = [s['nombre'] for s in resp.data]
        self.assertIn('Centro', nombres)

    def test_create_clase_scoped_to_user_gym(self):
        resp = self.client.post('/api/gyms/clases/', {
            'nombre': 'Boxeo Fundamentos', 'tipo': 'resistencia', 'profesor': 'Coach A',
            'hora_inicio': '18:00', 'hora_fin': '19:00', 'dias': 'lun,mie,vie',
        })
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        self.assertEqual(resp.data['gym'], self.gym.id)

    def test_list_gyms(self):
        resp = self.client.get('/api/gyms/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        nombres = [g['nombre'] for g in resp.data]
        self.assertIn('Round3 Boxing', nombres)

    def test_gym_detail_incluye_sucursales(self):
        resp = self.client.get(f'/api/gyms/{self.gym.id}/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data['sucursales']), 1)
        self.assertEqual(resp.data['sucursales'][0]['nombre'], 'Centro')

    def test_recepcion_no_puede_crear_gym(self):
        recepcion = Usuario.objects.create_user(
            email='recep@round3.com', password='Passw0rd1', nombre='Recep',
            rol='recepcion', gym=self.gym,
        )
        self.authenticate(recepcion)
        resp = self.client.post('/api/gyms/', {'nombre': 'Gym Pirata', 'tipo': 'box'})
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_recepcion_si_puede_leer_gyms(self):
        recepcion = Usuario.objects.create_user(
            email='recep@round3.com', password='Passw0rd1', nombre='Recep',
            rol='recepcion', gym=self.gym,
        )
        self.authenticate(recepcion)
        resp = self.client.get('/api/gyms/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)


class MultitenantGymTests(BaseAPITestCase):
    """Un negocio no puede ver ni tocar la información de otro negocio."""

    def test_admin_no_ve_otros_gyms_en_lista(self):
        resp = self.client.get('/api/gyms/')
        nombres = [g['nombre'] for g in resp.data]
        self.assertIn('Round3 Boxing', nombres)
        self.assertNotIn('Otro Gym', nombres)

    def test_admin_no_ve_detalle_de_otro_gym(self):
        resp = self.client.get(f'/api/gyms/{self.otro_gym.id}/')
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_admin_no_puede_editar_otro_gym(self):
        resp = self.client.patch(f'/api/gyms/{self.otro_gym.id}/', {'nombre': 'Hackeado'})
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
        self.otro_gym.refresh_from_db()
        self.assertEqual(self.otro_gym.nombre, 'Otro Gym')

    def test_admin_no_puede_borrar_otro_gym(self):
        resp = self.client.delete(f'/api/gyms/{self.otro_gym.id}/')
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(Gym.objects.filter(id=self.otro_gym.id).exists())

    def test_sucursales_de_otro_gym_ocultas(self):
        Sucursal.objects.create(gym=self.otro_gym, nombre='Sucursal Ajena')
        resp = self.client.get('/api/gyms/sucursales/')
        nombres = [s['nombre'] for s in resp.data]
        self.assertIn('Centro', nombres)
        self.assertNotIn('Sucursal Ajena', nombres)

    def test_admin_no_puede_editar_sucursal_de_otro_gym(self):
        ajena = Sucursal.objects.create(gym=self.otro_gym, nombre='Sucursal Ajena')
        resp = self.client.patch(f'/api/gyms/sucursales/{ajena.id}/', {'nombre': 'Tomada'})
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_superadmin_ve_todos_los_gyms(self):
        root = Usuario.objects.create_superuser(email='super@root.com', password='Passw0rd1', nombre='Root')
        self.authenticate(root)
        resp = self.client.get('/api/gyms/')
        nombres = [g['nombre'] for g in resp.data]
        self.assertIn('Round3 Boxing', nombres)
        self.assertIn('Otro Gym', nombres)


class EquipamientoTests(BaseAPITestCase):
    def test_create_equipamiento_scoped_to_gym(self):
        resp = self.client.post('/api/gyms/equipamiento/', {
            'nombre': 'Costal 100lb', 'categoria': 'impacto', 'cantidad': 4,
        })
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        self.assertEqual(resp.data['gym'], self.gym.id)

    def test_list_equipamiento_scoped_to_gym(self):
        Equipamiento.objects.create(gym=self.gym, nombre='Ring', categoria='infraestructura')
        Equipamiento.objects.create(gym=self.otro_gym, nombre='Caminadora', categoria='cardio')
        resp = self.client.get('/api/gyms/equipamiento/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        nombres = [e['nombre'] for e in resp.data]
        self.assertIn('Ring', nombres)
        self.assertNotIn('Caminadora', nombres)

    def test_recepcion_no_accede_equipamiento(self):
        recepcion = Usuario.objects.create_user(
            email='recep@round3.com', password='Passw0rd1', nombre='Recep',
            rol='recepcion', gym=self.gym,
        )
        self.authenticate(recepcion)
        resp = self.client.get('/api/gyms/equipamiento/')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_delete_equipamiento(self):
        eq = Equipamiento.objects.create(gym=self.gym, nombre='Ring', categoria='infraestructura')
        resp = self.client.delete(f'/api/gyms/equipamiento/{eq.id}/')
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)
