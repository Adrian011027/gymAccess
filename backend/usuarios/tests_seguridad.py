"""Regresión de la auditoría del 2026-08-23 (`auditoria_seguridad_2026-08-23.md`).

Un test por hallazgo crítico. Todos fallaban antes del arreglo, y cada uno se
escribió reproduciendo la petición exacta con la que se verificó el agujero contra
la API corriendo —no una versión aproximada—.

Existen porque estos huecos no son errores de lógica visibles: son campos que un
`ModelSerializer` expone por omisión y validaciones que están en `get_queryset` pero
no en la escritura. Un refactor bienintencionado los reabre sin que nadie lo note.
"""

from django.core.cache import cache
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from gyms.models import Gym, Sucursal
from gyms.tests import BaseAPITestCase
from socios.models import Plan
from usuarios.models import Usuario

PASS_VALIDA = 'tejocote-ancla-71'


class EscaladaDePrivilegiosTests(BaseAPITestCase):
    """Hallazgo 1: el admin de un gym se ascendía a superadmin y se quedaba el SaaS."""

    def test_admin_no_se_asciende_a_superadmin(self):
        resp = self.client.patch(f'/api/usuarios/{self.user.id}/', {'rol': 'superadmin'})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.user.refresh_from_db()
        self.assertEqual(self.user.rol, 'admin')

    def test_el_ascenso_bloqueado_no_abre_el_panel_saas(self):
        """La prueba que importa: 403 antes y 403 después del intento.

        El ascenso surtía efecto con el MISMO token, sin volver a iniciar sesión,
        porque `EsSuperAdmin` lee el rol de la base y no del JWT.
        """
        self.assertEqual(self.client.get('/api/saas/resumen/').status_code,
                         status.HTTP_403_FORBIDDEN)
        self.client.patch(f'/api/usuarios/{self.user.id}/', {'rol': 'superadmin'})
        self.assertEqual(self.client.get('/api/saas/resumen/').status_code,
                         status.HTTP_403_FORBIDDEN)

    def test_admin_no_crea_superadmins(self):
        resp = self.client.post('/api/usuarios/', {
            'email': 'colado@round3.com', 'password': PASS_VALIDA,
            'nombre': 'Colado', 'rol': 'superadmin',
        })
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(Usuario.objects.filter(email='colado@round3.com').exists())

    def test_admin_si_puede_nombrar_a_otro_admin(self):
        """Lo que se cierra es el ascenso propio, no la gestión normal del gym."""
        otro = Usuario.objects.create_user(
            email='recep@round3.com', password='Passw0rd1', nombre='Recep',
            rol='recepcion', gym=self.gym, sucursal=self.sucursal,
        )
        resp = self.client.patch(f'/api/usuarios/{otro.id}/', {'rol': 'admin'})
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        otro.refresh_from_db()
        self.assertEqual(otro.rol, 'admin')

    def test_admin_no_edita_la_cuenta_de_un_superadmin(self):
        """Cambiarle la contraseña a un superadmin es tomar su cuenta."""
        jefe = Usuario.objects.create_user(
            email='jefe@saas.com', password='Passw0rd1', nombre='Jefe',
            rol='superadmin', gym=self.gym,
        )
        resp = self.client.patch(f'/api/usuarios/{jefe.id}/', {'password': PASS_VALIDA})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        jefe.refresh_from_db()
        self.assertTrue(jefe.check_password('Passw0rd1'))


class AislamientoEntreGymsTests(BaseAPITestCase):
    """Hallazgos 2 y 3: `gym` escribible y escrituras cruzadas."""

    def test_admin_no_se_muda_a_otro_gym(self):
        resp = self.client.patch(f'/api/usuarios/{self.user.id}/',
                                 {'gym': self.otro_gym.id})
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        # El PATCH se acepta pero el campo se ignora: mudarse era leer el negocio
        # de al lado con el mismo token, porque a partir de ahí el scoping ayuda.
        self.user.refresh_from_db()
        self.assertEqual(self.user.gym_id, self.gym.id)

    def test_no_crea_empleados_con_sucursal_de_otro_gym(self):
        ajena = Sucursal.objects.create(gym=self.otro_gym, nombre='Ajena')
        resp = self.client.post('/api/usuarios/', {
            'email': 'topo@round3.com', 'password': PASS_VALIDA, 'nombre': 'Topo',
            'rol': 'recepcion', 'sucursal': ajena.id,
        })
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_no_crea_sucursales_en_otro_gym(self):
        resp = self.client.post('/api/gyms/sucursales/', {
            'nombre': 'Sucursal inyectada', 'gym': self.otro_gym.id,
        })
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        creada = Sucursal.objects.get(nombre='Sucursal inyectada')
        self.assertEqual(creada.gym_id, self.gym.id)

    def test_no_mueve_una_sucursal_a_otro_gym(self):
        self.client.patch(f'/api/gyms/sucursales/{self.sucursal.id}/',
                          {'gym': self.otro_gym.id})
        self.sucursal.refresh_from_db()
        self.assertEqual(self.sucursal.gym_id, self.gym.id)

    def test_no_crea_planes_en_otro_gym(self):
        resp = self.client.post('/api/socios/planes/', {
            'nombre': 'Plan inyectado', 'tipo': 'mensual', 'precio': '1.00',
            'duracion_dias': 30, 'gym': self.otro_gym.id,
        })
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        self.assertEqual(Plan.objects.get(nombre='Plan inyectado').gym_id, self.gym.id)

    def test_sucursal_se_da_de_baja_sin_borrarse(self):
        """De una sucursal cuelgan accesos y ventas: el histórico tiene que cuadrar."""
        resp = self.client.delete(f'/api/gyms/sucursales/{self.sucursal.id}/')
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)
        self.sucursal.refresh_from_db()
        self.assertFalse(self.sucursal.activa)


class PoliticaDeContrasenasTests(BaseAPITestCase):
    """Hallazgo 5: `AUTH_PASSWORD_VALIDATORS` estaba configurado y no corría."""

    def test_rechaza_contrasena_de_un_caracter(self):
        resp = self.client.post('/api/usuarios/', {
            'email': 'debil@round3.com', 'password': '1', 'nombre': 'Debil',
            'rol': 'admin',
        })
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('password', resp.data)
        self.assertFalse(Usuario.objects.filter(email='debil@round3.com').exists())

    def test_rechaza_contrasena_comun(self):
        resp = self.client.post('/api/usuarios/', {
            'email': 'comun@round3.com', 'password': 'password123', 'nombre': 'Comun',
            'rol': 'admin',
        })
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_tambien_valida_al_cambiarla(self):
        otro = Usuario.objects.create_user(
            email='recep2@round3.com', password='Passw0rd1', nombre='Recep',
            rol='recepcion', gym=self.gym, sucursal=self.sucursal,
        )
        resp = self.client.patch(f'/api/usuarios/{otro.id}/', {'password': '1'})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        otro.refresh_from_db()
        self.assertTrue(otro.check_password('Passw0rd1'))


class GymSuspendidoTests(BaseAPITestCase):
    """Hallazgo 6: suspender a un moroso no le cortaba nada."""

    def suspender(self):
        self.gym.activo = False
        self.gym.save(update_fields=['activo'])

    def test_el_token_ya_emitido_deja_de_servir(self):
        self.assertEqual(self.client.get('/api/socios/').status_code, status.HTTP_200_OK)
        self.suspender()
        self.assertEqual(self.client.get('/api/socios/').status_code,
                         status.HTTP_401_UNAUTHORIZED)

    def test_no_puede_volver_a_iniciar_sesion(self):
        self.suspender()
        cliente = APIClient()
        resp = cliente.post(reverse('token_obtain'), {
            'email': self.user.email, 'password': 'Passw0rd1',
        })
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_el_superadmin_del_saas_sigue_entrando(self):
        """No tiene gym, y es quien tiene que poder reactivar al que ya pagó."""
        self.suspender()
        jefe = Usuario.objects.create_user(
            email='jefe@saas.com', password='Passw0rd1', nombre='Jefe', rol='superadmin',
        )
        cliente = APIClient()
        cache.clear()
        resp = cliente.post(reverse('token_obtain'), {
            'email': jefe.email, 'password': 'Passw0rd1',
        })
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        cliente.credentials(HTTP_AUTHORIZATION=f"Bearer {resp.data['access']}")
        self.assertEqual(cliente.get('/api/saas/resumen/').status_code,
                         status.HTTP_200_OK)

    def test_reactivar_devuelve_el_acceso(self):
        self.suspender()
        Gym.objects.filter(id=self.gym.id).update(activo=True)
        self.assertEqual(self.client.get('/api/socios/').status_code, status.HTTP_200_OK)


class TokenQRTests(BaseAPITestCase):
    """Hallazgo 11: 9 000 combinaciones por socio, con `random` y un id secuencial."""

    def test_el_token_no_es_adivinable(self):
        from accesos.models import generar_token_qr

        PREFIJO = 'R3B-QR-00001-'
        tokens = {generar_token_qr(1) for _ in range(200)}
        self.assertEqual(len(tokens), 200, 'el token se repite: entropía insuficiente')
        # El prefijo se conserva porque hay pantallas y tests que lo muestran.
        self.assertTrue(all(t.startswith(PREFIJO) for t in tokens))
        # La parte aleatoria tiene que ser mucho más larga que los 4 dígitos de antes.
        #
        # Se recorta por la longitud del prefijo y NO con `rsplit('-', 1)`: el
        # alfabeto de `token_urlsafe` incluye el guion, así que un rsplit parte
        # dentro de la parte aleatoria y devuelve un trozo corto. Con ~22% de los
        # tokens llevando un guion, este test fallaba una de cada cuatro corridas
        # —y el código estaba bien; el que medía mal era el test—.
        for t in tokens:
            self.assertGreaterEqual(len(t[len(PREFIJO):]), 16)
