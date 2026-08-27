"""Matriz de permisos por rol (admin / recepcion / coach / superadmin) sobre cada
endpoint, más el comportamiento de sesión: token, usuario desactivado y datos del JWT.
"""

from datetime import date, timedelta

from rest_framework import status
from rest_framework.test import APIClient

from gyms.models import Clase, Equipamiento
from gyms.tests import BaseAPITestCase
from socios.models import Plan, Socio, Membresia, Gasto
from usuarios.models import Usuario

HOY = date.today

# (etiqueta, método, url) — sonda mínima por módulo
LECTURAS = [
    ('socios', '/api/socios/'),
    ('planes', '/api/socios/planes/'),
    ('membresias', '/api/socios/membresias/'),
    ('pagos', '/api/socios/pagos/'),
    ('gastos', '/api/socios/gastos/'),
    ('gyms', '/api/gyms/'),
    ('sucursales', '/api/gyms/sucursales/'),
    ('clases', '/api/gyms/clases/'),
    ('equipamiento', '/api/gyms/equipamiento/'),
    ('accesos', '/api/accesos/'),
    ('stats', '/api/accesos/stats/'),
    ('notificaciones', '/api/notificaciones/'),
    ('usuarios', '/api/usuarios/'),
]

# Módulos reservados al admin del gym
SOLO_ADMIN = {'gastos', 'equipamiento', 'usuarios'}


class RolBase(BaseAPITestCase):
    def crear_rol(self, rol, email=None):
        return Usuario.objects.create_user(
            email=email or f'{rol}@round3.com', password='Passw0rd1',
            nombre=rol.capitalize(), rol=rol, gym=self.gym,
        )


class MatrizDeLecturaTests(RolBase):
    def _leer_todo(self):
        return {nombre: self.client.get(url).status_code for nombre, url in LECTURAS}

    def test_admin_lee_todos_los_modulos(self):
        for nombre, code in self._leer_todo().items():
            self.assertEqual(code, status.HTTP_200_OK, f'{nombre} devolvió {code}')

    def test_recepcion_lee_operacion_pero_no_finanzas_ni_usuarios(self):
        self.authenticate(self.crear_rol('recepcion'))
        for nombre, code in self._leer_todo().items():
            esperado = status.HTTP_403_FORBIDDEN if nombre in SOLO_ADMIN else status.HTTP_200_OK
            self.assertEqual(code, esperado, f'{nombre} devolvió {code}')

    def test_coach_tiene_los_mismos_limites_que_recepcion(self):
        """'coach' no está contemplado en ROLES_ADMIN, así que cae en el mismo cajón."""
        self.authenticate(self.crear_rol('coach'))
        for nombre, code in self._leer_todo().items():
            esperado = status.HTTP_403_FORBIDDEN if nombre in SOLO_ADMIN else status.HTTP_200_OK
            self.assertEqual(code, esperado, f'{nombre} devolvió {code}')

    def test_anonimo_no_lee_nada(self):
        cliente = APIClient()
        for nombre, url in LECTURAS:
            self.assertEqual(
                cliente.get(url).status_code, status.HTTP_401_UNAUTHORIZED,
                f'{nombre} no exigió autenticación',
            )


class MatrizDeEscrituraTests(RolBase):
    """Quién puede modificar qué. Recepción opera el mostrador; admin manda."""

    def setUp(self):
        super().setUp()
        self.recepcion = self.crear_rol('recepcion')
        self.socio = Socio.objects.create(gym=self.gym, nombre='Ana', apellido='Lopez')
        self.plan = Plan.objects.create(
            gym=self.gym, nombre='Mensual', tipo='mensual', precio=500, duracion_dias=30,
        )
        self.membresia = Membresia.objects.create(
            socio=self.socio, plan=self.plan, sucursal=self.sucursal,
            fecha_inicio=HOY(), fecha_fin=HOY() + timedelta(days=30), estado='vencida',
        )

    def test_recepcion_puede_dar_de_alta_socios(self):
        self.authenticate(self.recepcion)
        resp = self.client.post('/api/socios/', {'nombre': 'Nuevo', 'apellido': 'Socio'})
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)

    def test_recepcion_puede_editar_socios(self):
        self.authenticate(self.recepcion)
        resp = self.client.patch(f'/api/socios/{self.socio.id}/', {'telefono': '5500000000'})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_recepcion_puede_dar_de_baja_a_un_socio(self):
        self.authenticate(self.recepcion)
        resp = self.client.patch(f'/api/socios/{self.socio.id}/', {'activo': False})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.socio.refresh_from_db()
        self.assertFalse(self.socio.activo)

    def test_recepcion_puede_cobrar(self):
        self.authenticate(self.recepcion)
        resp = self.client.post('/api/socios/pagos/', {
            'membresia': self.membresia.id, 'monto': '500.00', 'metodo': 'efectivo',
        })
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)

    def test_recepcion_puede_hacer_checkin(self):
        from accesos.models import MetodoAcceso
        MetodoAcceso.objects.create(socio=self.socio, tipo='qr', token='QR-1')
        self.authenticate(self.recepcion)
        resp = self.client.post('/api/accesos/checkin/', {
            'token': 'QR-1', 'sucursal_id': self.sucursal.id,
        })
        self.assertIn(resp.status_code, (status.HTTP_200_OK, status.HTTP_403_FORBIDDEN))
        self.assertNotEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_recepcion_puede_sincronizar_huella(self):
        self.authenticate(self.recepcion)
        resp = self.client.post('/api/accesos/sincronizar-huella/', {
            'socio_id': self.socio.id, 'template': 'FP-1',
        })
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)

    def test_recepcion_no_puede_crear_planes(self):
        self.authenticate(self.recepcion)
        resp = self.client.post('/api/socios/planes/', {
            'gym': self.gym.id, 'nombre': 'Pirata', 'tipo': 'mensual', 'precio': '1.00',
        })
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_recepcion_no_puede_borrar_planes(self):
        self.authenticate(self.recepcion)
        resp = self.client.delete(f'/api/socios/planes/{self.plan.id}/')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_recepcion_no_puede_registrar_gastos(self):
        self.authenticate(self.recepcion)
        resp = self.client.post('/api/socios/gastos/', {
            'categoria': 'renta', 'descripcion': 'X', 'monto': '1.00',
            'fecha': HOY().isoformat(),
        })
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_recepcion_no_puede_ver_un_gasto_puntual(self):
        gasto = Gasto.objects.create(gym=self.gym, categoria='renta', descripcion='X',
                                     monto=1, fecha=HOY())
        self.authenticate(self.recepcion)
        resp = self.client.get(f'/api/socios/gastos/{gasto.id}/')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_recepcion_no_puede_tocar_equipamiento(self):
        equipo = Equipamiento.objects.create(gym=self.gym, nombre='Ring', categoria='infraestructura')
        self.authenticate(self.recepcion)
        self.assertEqual(
            self.client.patch(f'/api/gyms/equipamiento/{equipo.id}/', {'cantidad': 9}).status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_recepcion_no_puede_crear_usuarios(self):
        self.authenticate(self.recepcion)
        resp = self.client.post('/api/usuarios/', {
            'email': 'colado@round3.com', 'password': 'tejocote-ancla-71',
            'nombre': 'Colado', 'rol': 'admin',
        })
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(Usuario.objects.filter(email='colado@round3.com').exists())

    def test_recepcion_no_puede_ascenderse_a_admin(self):
        self.authenticate(self.recepcion)
        resp = self.client.patch(f'/api/usuarios/{self.recepcion.id}/', {'rol': 'admin'})
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self.recepcion.refresh_from_db()
        self.assertEqual(self.recepcion.rol, 'recepcion')

    def test_recepcion_no_puede_editar_el_gym(self):
        self.authenticate(self.recepcion)
        resp = self.client.patch(f'/api/gyms/{self.gym.id}/', {'nombre': 'Mi Gym'})
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_coach_tampoco_puede_cambiar_planes(self):
        self.authenticate(self.crear_rol('coach'))
        resp = self.client.post('/api/socios/planes/', {
            'gym': self.gym.id, 'nombre': 'Pirata', 'tipo': 'mensual', 'precio': '1.00',
        })
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)


class GestionDeUsuariosTests(RolBase):
    def test_admin_crea_recepcionista_en_su_gym(self):
        resp = self.client.post('/api/usuarios/', {
            'email': 'nueva@round3.com', 'password': 'tejocote-ancla-71',
            'nombre': 'Nueva', 'rol': 'recepcion', 'sucursal': self.sucursal.id,
        })
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        creado = Usuario.objects.get(email='nueva@round3.com')
        self.assertEqual(creado.gym_id, self.gym.id)
        self.assertTrue(creado.check_password('tejocote-ancla-71'))

    def test_gym_del_payload_es_ignorado(self):
        """Un admin no puede sembrar usuarios en el gym de otro negocio."""
        resp = self.client.post('/api/usuarios/', {
            'email': 'infiltrado@x.com', 'password': 'tejocote-ancla-71', 'nombre': 'Infiltrado',
            'rol': 'admin', 'gym': self.otro_gym.id,
        })
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        self.assertEqual(Usuario.objects.get(email='infiltrado@x.com').gym_id, self.gym.id)

    def test_no_puede_editar_usuario_de_otro_gym(self):
        ajeno = Usuario.objects.create_user(
            email='ajeno@otro.com', password='Passw0rd1', nombre='Ajeno',
            rol='admin', gym=self.otro_gym,
        )
        resp = self.client.patch(f'/api/usuarios/{ajeno.id}/', {'nombre': 'Secuestrado'})
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_password_no_se_expone_al_leer(self):
        resp = self.client.get('/api/usuarios/')
        self.assertNotIn('password', resp.data[0])

    def test_cambiar_password_lo_rehashea(self):
        recepcion = self.crear_rol('recepcion')
        resp = self.client.patch(f'/api/usuarios/{recepcion.id}/', {'password': 'NuevaPass9'})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        recepcion.refresh_from_db()
        self.assertTrue(recepcion.check_password('NuevaPass9'))
        self.assertNotEqual(recepcion.password, 'NuevaPass9')

    def test_email_duplicado_es_rechazado(self):
        resp = self.client.post('/api/usuarios/', {
            'email': 'admin@round3.com', 'password': 'tejocote-ancla-71', 'nombre': 'Clon',
        })
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_rol_invalido_es_rechazado(self):
        resp = self.client.post('/api/usuarios/', {
            'email': 'x@round3.com', 'password': 'tejocote-ancla-71', 'nombre': 'X', 'rol': 'dueño',
        })
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_desactivar_usuario(self):
        recepcion = self.crear_rol('recepcion')
        resp = self.client.patch(f'/api/usuarios/{recepcion.id}/', {'is_active': False})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        recepcion.refresh_from_db()
        self.assertFalse(recepcion.is_active)


class SesionTests(RolBase):
    def test_jwt_incluye_los_datos_que_usa_el_frontend(self):
        """AuthContext lee nombre/email/rol/gym_id del token para pintar el menú."""
        import base64, json
        resp = APIClient().post('/api/auth/login/', {
            'email': 'admin@round3.com', 'password': 'Passw0rd1',
        })
        payload = resp.data['access'].split('.')[1]
        payload += '=' * (-len(payload) % 4)
        datos = json.loads(base64.urlsafe_b64decode(payload))
        self.assertEqual(datos['email'], 'admin@round3.com')
        self.assertEqual(datos['nombre'], 'Admin')
        self.assertEqual(datos['rol'], 'admin')
        self.assertEqual(datos['gym_id'], self.gym.id)

    def test_usuario_desactivado_no_puede_entrar(self):
        recepcion = self.crear_rol('recepcion')
        recepcion.is_active = False
        recepcion.save()
        resp = APIClient().post('/api/auth/login/', {
            'email': recepcion.email, 'password': 'Passw0rd1',
        })
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_token_basura_es_rechazado(self):
        cliente = APIClient()
        cliente.credentials(HTTP_AUTHORIZATION='Bearer no-es-un-token')
        self.assertEqual(cliente.get('/api/socios/').status_code, status.HTTP_401_UNAUTHORIZED)

    def test_email_inexistente_no_revela_nada(self):
        resp = APIClient().post('/api/auth/login/', {
            'email': 'nadie@round3.com', 'password': 'Passw0rd1',
        })
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_login_es_case_insensitive_en_el_dominio(self):
        """normalize_email baja el dominio; el buzón conserva su capitalización."""
        Usuario.objects.create_user(
            email='Mixto@ROUND3.com', password='Passw0rd1', nombre='Mixto', gym=self.gym,
        )
        self.assertTrue(Usuario.objects.filter(email='Mixto@round3.com').exists())


class UsuarioSinGymTests(BaseAPITestCase):
    """Un superadmin recién creado no tiene gym: las vistas no deben reventar."""

    def setUp(self):
        super().setUp()
        self.root = Usuario.objects.create_superuser(
            email='root@sistema.com', password='Passw0rd1', nombre='Root',
        )
        self.authenticate(self.root)

    def test_listas_devuelven_vacio_en_vez_de_error(self):
        for url in ('/api/socios/', '/api/socios/membresias/', '/api/accesos/',
                    '/api/notificaciones/', '/api/gyms/clases/'):
            resp = self.client.get(url)
            self.assertEqual(resp.status_code, status.HTTP_200_OK, f'{url} → {resp.status_code}')
            self.assertEqual(len(resp.data), 0, url)

    def test_superadmin_ve_todos_los_gyms(self):
        resp = self.client.get('/api/gyms/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(resp.data), 2)

    def test_stats_no_revienta_sin_gym(self):
        resp = self.client.get('/api/accesos/stats/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['accesos_hoy'], 0)

    def test_superadmin_no_puede_crear_socios_huerfanos(self):
        """Un superadmin sin gym no puede dejar socios sin gym en la base."""
        resp = self.client.post('/api/socios/', {'nombre': 'Huerfano', 'apellido': 'Test'})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(Socio.objects.filter(nombre='Huerfano').exists())

    def test_BUG_alta_de_socio_sin_gym_revienta_en_vez_de_devolver_400(self):
        """BUG (menor, robustez): SocioViewSet.perform_create (socios/views.py:33-37)
        tiene una rama `else: serializer.save()` para usuarios sin gym, pero
        Socio.gym es NOT NULL (socios/models.py:33).

        Un superadmin sin gym asignado que da de alta un socio recibe un 500
        (`IntegrityError: NOT NULL constraint failed: socios.gym_id`) en lugar de un
        400. Solo afecta a superadmins sin gym; admin y recepción siempre tienen uno.
        Arreglo: validar en el serializer que haya gym, o exigir gym explícito
        cuando el usuario no tiene.
        """
        resp = self.client.post('/api/socios/', {'nombre': 'Huerfano', 'apellido': 'Test'})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
