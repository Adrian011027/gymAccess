"""Eliminar un empleado: desaparece del sistema en el acto y se borra a los 30 días."""

from datetime import timedelta
from io import StringIO

from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from gyms.tests import BaseAPITestCase
from legal.models import DocumentoLegal
from usuarios.models import Usuario


class EliminarEmpleadoTests(BaseAPITestCase):
    def setUp(self):
        super().setUp()
        self.empleado = Usuario.objects.create_user(
            email='recepcion@round3.com', password='Passw0rd1', nombre='Recepción',
            rol='recepcion', gym=self.gym, sucursal=self.sucursal,
        )
        self.empleado.sucursales_permitidas.add(self.sucursal)
        self.url = f'/api/usuarios/{self.empleado.id}/'

    def eliminar(self):
        return self.client.delete(self.url)

    def test_eliminar_lo_desactiva_y_guarda_la_fecha(self):
        resp = self.eliminar()

        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)
        self.empleado.refresh_from_db()
        self.assertFalse(self.empleado.is_active)
        self.assertIsNotNone(self.empleado.eliminado_en)

    def test_no_aparece_en_el_listado_ni_pidiendo_las_bajas(self):
        self.eliminar()

        for url in ('/api/usuarios/', '/api/usuarios/?incluir_bajas=1'):
            ids = [u['id'] for u in self.client.get(url).data]
            self.assertNotIn(self.empleado.id, ids, url)

    def test_no_se_puede_consultar_ni_editar(self):
        self.eliminar()

        self.assertEqual(self.client.get(self.url).status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(
            self.client.patch(self.url, {'is_active': True}, format='json').status_code,
            status.HTTP_404_NOT_FOUND,
        )

    def test_no_puede_iniciar_sesion(self):
        self.eliminar()

        resp = APIClient().post(reverse('token_obtain'), {
            'email': 'recepcion@round3.com', 'password': 'Passw0rd1',
        })

        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_la_sesion_que_ya_tenia_deja_de_servir(self):
        sesion = APIClient()
        token = sesion.post(reverse('token_obtain'), {
            'email': 'recepcion@round3.com', 'password': 'Passw0rd1',
        }).data['access']
        sesion.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        self.assertEqual(sesion.get('/api/socios/').status_code, status.HTTP_200_OK)

        self.eliminar()

        self.assertEqual(sesion.get('/api/socios/').status_code, status.HTTP_401_UNAUTHORIZED)

    def test_su_correo_se_puede_volver_a_dar_de_alta(self):
        """Recontratar a alguien no debe chocar con una cuenta que ya no existe."""
        self.eliminar()

        resp = self.client.post('/api/usuarios/', {
            'email': 'recepcion@round3.com', 'nombre': 'Recepción nueva', 'rol': 'recepcion',
            'sucursal': self.sucursal.id, 'sucursales_permitidas': [self.sucursal.id],
            'password': 'OtraClave#2026',
        }, format='json')

        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        self.assertFalse(Usuario.objects.filter(id=self.empleado.id).exists())
        self.assertTrue(Usuario.objects.get(email='recepcion@round3.com').is_active)

    def test_el_correo_de_un_empleado_vigente_sigue_ocupado(self):
        resp = self.client.post('/api/usuarios/', {
            'email': 'RECEPCION@round3.com', 'nombre': 'Duplicado', 'rol': 'recepcion',
            'sucursal': self.sucursal.id, 'sucursales_permitidas': [self.sucursal.id],
            'password': 'OtraClave#2026',
        }, format='json')

        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('email', resp.data)


class PurgaDeEmpleadosTests(BaseAPITestCase):
    def crear_eliminado(self, email, hace_dias):
        return Usuario.objects.create_user(
            email=email, password='Passw0rd1', nombre='Ex empleado', rol='recepcion',
            gym=self.gym, is_active=False,
            eliminado_en=timezone.now() - timedelta(days=hace_dias),
        )

    def purgar(self, *args):
        salida = StringIO()
        call_command('purgar_empleados_eliminados', *args, stdout=salida)
        return salida.getvalue()

    def test_borra_a_los_eliminados_hace_mas_de_30_dias(self):
        viejo = self.crear_eliminado('viejo@round3.com', hace_dias=31)

        self.purgar()

        self.assertFalse(Usuario.objects.filter(id=viejo.id).exists())

    def test_respeta_a_los_eliminados_hace_menos_de_30_dias(self):
        reciente = self.crear_eliminado('reciente@round3.com', hace_dias=29)

        self.purgar()

        self.assertTrue(Usuario.objects.filter(id=reciente.id).exists())

    def test_no_toca_a_empleados_vigentes_ni_a_inactivos_sin_eliminar(self):
        inactivo = Usuario.objects.create_user(
            email='inactivo@round3.com', password='Passw0rd1', nombre='Inactivo',
            rol='recepcion', gym=self.gym, is_active=False,
        )

        self.purgar()

        self.assertTrue(Usuario.objects.filter(id=self.user.id).exists())
        self.assertTrue(Usuario.objects.filter(id=inactivo.id).exists())

    def test_dry_run_no_borra_nada(self):
        viejo = self.crear_eliminado('viejo@round3.com', hace_dias=45)

        salida = self.purgar('--dry-run')

        self.assertIn('1 empleados se borrarían', salida)
        self.assertTrue(Usuario.objects.filter(id=viejo.id).exists())

    def test_lo_que_registro_se_conserva_sin_su_nombre(self):
        """Los registros (pagos, documentos…) se quedan: solo pierden al responsable."""
        viejo = self.crear_eliminado('viejo@round3.com', hace_dias=31)
        doc = DocumentoLegal.objects.create(
            gym=self.gym, tipo=DocumentoLegal.AVISO_PRIVACIDAD, version='1.0',
            titulo='Aviso', contenido='Texto', publicado_por=viejo,
        )

        self.purgar()

        doc.refresh_from_db()
        self.assertIsNone(doc.publicado_por)
