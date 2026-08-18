from rest_framework import status

from gyms.models import Sucursal
from usuarios.models import Usuario
from usuarios.tests_sucursal import BaseDosSucursales


class SucursalesPermitidasTests(BaseDosSucursales):
    """Un recepcionista puede rotar entre varias sucursales permitidas."""

    def setUp(self):
        super().setUp()
        self.recep_norte.sucursales_permitidas.set([self.centro, self.norte])

    def test_login_lleva_las_sucursales_permitidas(self):
        from django.urls import reverse
        import base64, json
        from django.core.cache import cache

        cache.clear()
        resp = self.client.post(reverse('token_obtain'), {
            'email': 'norte@round3.com', 'password': 'Passw0rd1',
        })
        payload = resp.data['access'].split('.')[1]
        payload += '=' * (-len(payload) % 4)
        datos = json.loads(base64.urlsafe_b64decode(payload))
        nombres = {s['nombre'] for s in datos['sucursales_permitidas']}
        self.assertEqual(nombres, {'Centro', 'Norte'})

    def test_puede_elegir_una_sucursal_permitida(self):
        self.authenticate(self.recep_norte)
        resp = self.client.post('/api/usuarios/sucursal-activa/', {'sucursal': self.centro.id})
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.recep_norte.refresh_from_db()
        self.assertEqual(self.recep_norte.sucursal_id, self.centro.id)

    def test_no_puede_elegir_sucursal_ajena(self):
        otra = Sucursal.objects.create(gym=self.gym, nombre='Otra')
        self.authenticate(self.recep_norte)
        resp = self.client.post('/api/usuarios/sucursal-activa/', {'sucursal': otra.id})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.recep_norte.refresh_from_db()
        self.assertEqual(self.recep_norte.sucursal_id, self.norte.id)

    def test_tokens_nuevos_reflejan_la_sucursal_elegida(self):
        import base64, json

        self.authenticate(self.recep_norte)
        resp = self.client.post('/api/usuarios/sucursal-activa/', {'sucursal': self.centro.id})
        payload = resp.data['access'].split('.')[1]
        payload += '=' * (-len(payload) % 4)
        datos = json.loads(base64.urlsafe_b64decode(payload))
        self.assertEqual(datos['sucursal_id'], self.centro.id)
        self.assertEqual(datos['sucursal_nombre'], 'Centro')


class UsuarioSerializerSucursalesTests(BaseDosSucursales):
    def test_admin_crea_empleado_con_varias_sucursales(self):
        self.authenticate(self.duenio)
        resp = self.client.post('/api/usuarios/', {
            'nombre': 'Rota', 'email': 'rota@round3.com', 'rol': 'recepcion',
            'gym': self.gym.id, 'sucursal': self.centro.id,
            'sucursales_permitidas': [self.centro.id, self.norte.id],
            'password': 'Passw0rd1',
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        creado = Usuario.objects.get(email='rota@round3.com')
        self.assertEqual(
            set(creado.sucursales_permitidas.values_list('id', flat=True)),
            {self.centro.id, self.norte.id},
        )

    def test_sucursal_activa_debe_estar_entre_las_permitidas(self):
        self.authenticate(self.duenio)
        resp = self.client.post('/api/usuarios/', {
            'nombre': 'Rota', 'email': 'rota2@round3.com', 'rol': 'recepcion',
            'gym': self.gym.id, 'sucursal': self.norte.id,
            'sucursales_permitidas': [self.centro.id],
            'password': 'Passw0rd1',
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_horario_semanal_debe_usar_sucursales_permitidas(self):
        self.authenticate(self.duenio)
        resp = self.client.post('/api/usuarios/', {
            'nombre': 'Rota', 'email': 'rota3@round3.com', 'rol': 'recepcion',
            'gym': self.gym.id, 'sucursal': self.centro.id,
            'sucursales_permitidas': [self.centro.id],
            'horario_semanal': {'lunes': self.norte.id},
            'password': 'Passw0rd1',
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
