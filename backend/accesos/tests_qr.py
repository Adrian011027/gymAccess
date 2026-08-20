"""Asignación del código QR de acceso.

Los socios nuevos ya reciben uno al darse de alta, pero los cargados antes de eso
pueden no tenerlo, y sin código el kiosco no puede identificarlos.
"""

from rest_framework import status

from accesos.models import MetodoAcceso
from gyms.tests import BaseAPITestCase
from socios.models import Socio


class AsignarQRTests(BaseAPITestCase):
    def setUp(self):
        super().setUp()
        self.socio = Socio.objects.create(
            gym=self.gym, sucursal=self.sucursal, nombre='Ana', apellido='Ruiz',
        )

    def test_asigna_qr_a_socio_sin_codigo(self):
        resp = self.client.post('/api/accesos/asignar-qr/', {'socio_id': self.socio.id})
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertTrue(resp.data['token'])
        self.assertEqual(MetodoAcceso.objects.filter(socio=self.socio, tipo='qr').count(), 1)

    def test_no_duplica_el_codigo_existente(self):
        """Llamar dos veces devuelve el mismo código: si generara uno nuevo, la
        credencial ya impresa del socio dejaría de servir."""
        primero = self.client.post('/api/accesos/asignar-qr/', {'socio_id': self.socio.id})
        segundo = self.client.post('/api/accesos/asignar-qr/', {'socio_id': self.socio.id})
        self.assertEqual(segundo.status_code, status.HTTP_200_OK)
        self.assertEqual(segundo.data['token'], primero.data['token'])
        self.assertEqual(MetodoAcceso.objects.filter(socio=self.socio, tipo='qr').count(), 1)

    def test_no_asigna_a_socio_de_otro_gym(self):
        ajeno = Socio.objects.create(gym=self.otro_gym, nombre='Beto', apellido='Paz')
        resp = self.client.post('/api/accesos/asignar-qr/', {'socio_id': ajeno.id})
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
        self.assertFalse(MetodoAcceso.objects.filter(socio=ajeno).exists())

    def test_exige_socio_id(self):
        resp = self.client.post('/api/accesos/asignar-qr/', {})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_requiere_autenticacion(self):
        from rest_framework.test import APIClient
        resp = APIClient().post('/api/accesos/asignar-qr/', {'socio_id': self.socio.id})
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)
