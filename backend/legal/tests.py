"""Aviso de privacidad generado desde la plantilla con los datos de cada gym."""

import re

from rest_framework import status

from gyms.tests import BaseAPITestCase
from legal.models import DocumentoLegal
from usuarios.models import Usuario

URL = '/api/legal/documentos/plantilla-aviso/'


class PlantillaAvisoTests(BaseAPITestCase):
    def completar_gym(self, **cambios):
        datos = {
            'razon_social': 'Boxeo Round Tres S.A. de C.V.',
            'direccion': 'Av. Estrella 123, Col. Centro, Guadalajara, Jal., C.P. 44100',
            'telefono': '33 2233 2046',
            'email_contacto': 'privacidad@round3.com',
            **cambios,
        }
        for campo, valor in datos.items():
            setattr(self.gym, campo, valor)
        self.gym.save()

    def test_sin_datos_dice_cuales_faltan(self):
        resp = self.client.get(URL)

        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            [f['campo'] for f in resp.data['faltantes']],
            ['razon_social', 'direccion', 'telefono', 'email_contacto'],
        )

    def test_un_dato_en_blanco_cuenta_como_faltante(self):
        self.completar_gym(telefono='   ')

        resp = self.client.get(URL)

        self.assertEqual([f['campo'] for f in resp.data['faltantes']], ['telefono'])

    def test_llena_la_plantilla_con_los_datos_del_gym(self):
        self.completar_gym()

        resp = self.client.get(URL)
        texto = resp.data['contenido']

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn('**Boxeo Round Tres S.A. de C.V.** («Round3 Boxing»)', texto)
        self.assertIn('Av. Estrella 123, Col. Centro, Guadalajara, Jal., C.P. 44100', texto)
        self.assertIn('privacidad@round3.com · 33 2233 2046', texto)
        self.assertIn('**Versión:** 1.0', texto)

    def test_no_quedan_huecos_sin_llenar(self):
        """Un "{{direccion}}" o un "[CORREO]" literal ante el socio invalida el aviso."""
        self.completar_gym()

        texto = self.client.get(URL).data['contenido']

        self.assertNotIn('{{', texto)
        self.assertIsNone(re.search(r'\[[A-ZÁÉÍÓÚ ]{3,}', texto))
        self.assertNotIn('Borrador', texto)

    def test_direccion_en_varias_lineas_queda_en_una(self):
        """Un salto en blanco dentro de **...** deja los asteriscos sueltos a la vista."""
        self.completar_gym(direccion='Av. Estrella 123\n\nCol. Centro')

        texto = self.client.get(URL).data['contenido']

        self.assertIn('**Av. Estrella 123 Col. Centro**', texto)

    def test_con_un_aviso_publicado_sugiere_la_version_siguiente(self):
        self.completar_gym()
        DocumentoLegal.objects.create(
            gym=self.gym, tipo=DocumentoLegal.AVISO_PRIVACIDAD, version='1.0',
            titulo='Aviso', contenido='Texto',
        )

        resp = self.client.get(URL)

        self.assertEqual(resp.data['version'], '2.0')
        self.assertIn('**Versión:** 2.0', resp.data['contenido'])

    def test_el_aviso_de_otro_gym_no_cuenta_para_la_version(self):
        self.completar_gym()
        DocumentoLegal.objects.create(
            gym=self.otro_gym, tipo=DocumentoLegal.AVISO_PRIVACIDAD, version='1.0',
            titulo='Aviso', contenido='Texto',
        )

        self.assertEqual(self.client.get(URL).data['version'], '1.0')

    def test_no_publica_nada_por_si_solo(self):
        """Solo devuelve el borrador: publicarlo es decisión del admin tras leerlo."""
        self.completar_gym()

        self.client.get(URL)

        self.assertFalse(DocumentoLegal.objects.filter(gym=self.gym).exists())

    def test_lo_generado_se_publica_y_queda_vigente(self):
        self.completar_gym()
        borrador = self.client.get(URL).data

        resp = self.client.post('/api/legal/documentos/', {
            'tipo': DocumentoLegal.AVISO_PRIVACIDAD, 'version': borrador['version'],
            'titulo': borrador['titulo'], 'contenido': borrador['contenido'],
            'vigente_desde': borrador['vigente_desde'],
        }, format='json')  # Como el frontend: en multipart, `activo` ausente se lee False.

        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        vigente = DocumentoLegal.vigente(DocumentoLegal.AVISO_PRIVACIDAD, self.gym.id)
        self.assertIn('Boxeo Round Tres S.A. de C.V.', vigente.contenido)

    def test_recepcion_no_puede_generarlo(self):
        self.completar_gym()
        recepcion = Usuario.objects.create_user(
            email='recepcion@round3.com', password='Passw0rd1', nombre='Recepción',
            rol='recepcion', gym=self.gym,
        )
        self.authenticate(recepcion)

        self.assertEqual(self.client.get(URL).status_code, status.HTTP_403_FORBIDDEN)

    def test_la_razon_social_se_guarda_desde_configuracion(self):
        resp = self.client.patch(f'/api/gyms/{self.gym.id}/', {'razon_social': 'Boxeo Round Tres S.A. de C.V.'})

        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.gym.refresh_from_db()
        self.assertEqual(self.gym.razon_social, 'Boxeo Round Tres S.A. de C.V.')
