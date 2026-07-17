from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status

from gyms.models import Gym, Sucursal
from usuarios.models import Usuario


class BaseAPITestCase(TestCase):
    """Base con gym + usuario autenticado, reusado en todos los apps."""

    def setUp(self):
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
