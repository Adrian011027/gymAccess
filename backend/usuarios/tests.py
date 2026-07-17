from rest_framework import status

from gyms.tests import BaseAPITestCase
from usuarios.models import Usuario


class UsuarioScopeTests(BaseAPITestCase):
    def test_admin_sees_only_own_gym_users(self):
        Usuario.objects.create_user(email='otro@gym.com', password='Passw0rd1', nombre='Otro', gym=self.otro_gym)
        resp = self.client.get('/api/usuarios/')
        emails = [u['email'] for u in resp.data]
        self.assertIn('admin@round3.com', emails)
        self.assertNotIn('otro@gym.com', emails)

    def test_admin_create_user_scoped_to_own_gym(self):
        resp = self.client.post('/api/usuarios/', {
            'email': 'nuevo@round3.com', 'password': 'Passw0rd1', 'nombre': 'Nuevo', 'rol': 'recepcion',
        })
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        creado = Usuario.objects.get(email='nuevo@round3.com')
        self.assertEqual(creado.gym_id, self.gym.id)

    def test_superadmin_sees_all_users(self):
        super_user = Usuario.objects.create_superuser(email='super@root.com', password='Passw0rd1', nombre='Root')
        Usuario.objects.create_user(email='otro@gym.com', password='Passw0rd1', nombre='Otro', gym=self.otro_gym)
        self.authenticate(super_user)
        resp = self.client.get('/api/usuarios/')
        emails = [u['email'] for u in resp.data]
        self.assertIn('otro@gym.com', emails)
        self.assertIn('admin@round3.com', emails)

    def test_password_is_hashed_on_create(self):
        resp = self.client.post('/api/usuarios/', {
            'email': 'nuevo2@round3.com', 'password': 'Passw0rd1', 'nombre': 'Nuevo', 'rol': 'recepcion',
        })
        creado = Usuario.objects.get(email='nuevo2@round3.com')
        self.assertNotEqual(creado.password, 'Passw0rd1')
        self.assertTrue(creado.check_password('Passw0rd1'))
