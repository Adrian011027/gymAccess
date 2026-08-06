"""Módulo de notificaciones: campanita, historial, archivado y retención a 15 días."""

import unittest
from datetime import timedelta
from io import StringIO

from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework import status

from gyms.models import Equipamiento
from gyms.tests import BaseAPITestCase
from notificaciones.models import Notificacion
from notificaciones.views import RETENCION_DIAS


def envejecer(noti, dias):
    """`creado_en` es auto_now_add, así que se reescribe por UPDATE directo."""
    Notificacion.objects.filter(pk=noti.pk).update(
        creado_en=timezone.now() - timedelta(days=dias)
    )
    noti.refresh_from_db()
    return noti


class NotificacionBase(BaseAPITestCase):
    def crear(self, mensaje='Algo pasó', gym=None, **kwargs):
        return Notificacion.objects.create(
            gym=gym or self.gym, mensaje=mensaje, **kwargs
        )


class NotificacionListaTests(NotificacionBase):
    def test_lista_vacia_al_inicio(self):
        resp = self.client.get('/api/notificaciones/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data), 0)

    def test_lista_devuelve_las_no_archivadas(self):
        self.crear('Primera')
        self.crear('Segunda')
        resp = self.client.get('/api/notificaciones/')
        mensajes = [n['mensaje'] for n in resp.data]
        self.assertCountEqual(mensajes, ['Primera', 'Segunda'])

    def test_lista_oculta_las_archivadas(self):
        self.crear('Visible')
        self.crear('Oculta', archivada=True)
        resp = self.client.get('/api/notificaciones/')
        mensajes = [n['mensaje'] for n in resp.data]
        self.assertIn('Visible', mensajes)
        self.assertNotIn('Oculta', mensajes)

    def test_orden_mas_reciente_primero(self):
        vieja = self.crear('Vieja')
        envejecer(vieja, 3)
        self.crear('Nueva')
        resp = self.client.get('/api/notificaciones/')
        self.assertEqual([n['mensaje'] for n in resp.data], ['Nueva', 'Vieja'])

    def test_notificaciones_de_otro_gym_ocultas(self):
        self.crear('Mia')
        self.crear('Ajena', gym=self.otro_gym)
        resp = self.client.get('/api/notificaciones/')
        mensajes = [n['mensaje'] for n in resp.data]
        self.assertIn('Mia', mensajes)
        self.assertNotIn('Ajena', mensajes)

    def test_no_puede_leer_notificacion_de_otro_gym(self):
        ajena = self.crear('Ajena', gym=self.otro_gym)
        resp = self.client.get(f'/api/notificaciones/{ajena.id}/')
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_requiere_autenticacion(self):
        from rest_framework.test import APIClient
        resp = APIClient().get('/api/notificaciones/')
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_recepcion_ve_las_notificaciones_del_gym(self):
        from usuarios.models import Usuario
        self.crear('Para todos')
        recepcion = Usuario.objects.create_user(
            email='recep@round3.com', password='Passw0rd1', nombre='Recep',
            rol='recepcion', gym=self.gym,
        )
        self.authenticate(recepcion)
        resp = self.client.get('/api/notificaciones/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data), 1)


class NotificacionHistorialTests(NotificacionBase):
    def test_historial_incluye_archivadas(self):
        self.crear('Activa')
        self.crear('Archivada', archivada=True)
        resp = self.client.get('/api/notificaciones/historial/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        mensajes = [n['mensaje'] for n in resp.data]
        self.assertCountEqual(mensajes, ['Activa', 'Archivada'])

    def test_historial_scoped_al_gym(self):
        self.crear('Mia', archivada=True)
        self.crear('Ajena', gym=self.otro_gym, archivada=True)
        resp = self.client.get('/api/notificaciones/historial/')
        self.assertEqual([n['mensaje'] for n in resp.data], ['Mia'])


class NotificacionAccionesTests(NotificacionBase):
    def test_marcar_todas_leidas(self):
        a = self.crear('Una')
        b = self.crear('Dos')
        resp = self.client.post('/api/notificaciones/marcar-todas-leidas/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        a.refresh_from_db(); b.refresh_from_db()
        self.assertTrue(a.leida)
        self.assertTrue(b.leida)

    def test_marcar_todas_leidas_no_toca_otro_gym(self):
        ajena = self.crear('Ajena', gym=self.otro_gym)
        self.client.post('/api/notificaciones/marcar-todas-leidas/')
        ajena.refresh_from_db()
        self.assertFalse(ajena.leida)

    def test_limpiar_archiva_sin_borrar(self):
        noti = self.crear('Se archiva')
        resp = self.client.post('/api/notificaciones/limpiar/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        noti.refresh_from_db()
        self.assertTrue(noti.archivada)
        self.assertTrue(noti.leida)
        self.assertTrue(Notificacion.objects.filter(pk=noti.pk).exists())

    def test_limpiar_las_saca_de_la_campanita_pero_no_del_historial(self):
        self.crear('Se archiva')
        self.client.post('/api/notificaciones/limpiar/')
        self.assertEqual(len(self.client.get('/api/notificaciones/').data), 0)
        self.assertEqual(len(self.client.get('/api/notificaciones/historial/').data), 1)

    def test_limpiar_no_toca_otro_gym(self):
        ajena = self.crear('Ajena', gym=self.otro_gym)
        self.client.post('/api/notificaciones/limpiar/')
        ajena.refresh_from_db()
        self.assertFalse(ajena.archivada)

    def test_marcar_una_como_leida(self):
        noti = self.crear('Una')
        resp = self.client.patch(f'/api/notificaciones/{noti.id}/', {'leida': True})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        noti.refresh_from_db()
        self.assertTrue(noti.leida)

    def test_no_puede_editar_notificacion_de_otro_gym(self):
        ajena = self.crear('Ajena', gym=self.otro_gym)
        resp = self.client.patch(f'/api/notificaciones/{ajena.id}/', {'leida': True})
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_mensaje_no_es_editable(self):
        """El texto lo escribe el sistema, no el usuario (read_only en el serializer)."""
        noti = self.crear('Original')
        self.client.patch(f'/api/notificaciones/{noti.id}/', {'mensaje': 'Falsificado'})
        noti.refresh_from_db()
        self.assertEqual(noti.mensaje, 'Original')

    def test_delete_no_esta_permitido(self):
        noti = self.crear('Una')
        resp = self.client.delete(f'/api/notificaciones/{noti.id}/')
        self.assertEqual(resp.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        self.assertTrue(Notificacion.objects.filter(pk=noti.pk).exists())


class NotificacionRetencionTests(NotificacionBase):
    """Purga automática al listar: nada sobrevive más de RETENCION_DIAS."""

    def test_purga_las_mas_viejas_que_la_retencion(self):
        vieja = self.crear('Vieja')
        envejecer(vieja, RETENCION_DIAS + 1)
        self.crear('Reciente')
        resp = self.client.get('/api/notificaciones/')
        self.assertEqual([n['mensaje'] for n in resp.data], ['Reciente'])
        self.assertFalse(Notificacion.objects.filter(pk=vieja.pk).exists())

    def test_conserva_las_de_ayer(self):
        ayer = self.crear('Ayer')
        envejecer(ayer, 1)
        self.client.get('/api/notificaciones/')
        self.assertTrue(Notificacion.objects.filter(pk=ayer.pk).exists())

    def test_conserva_justo_en_el_limite(self):
        borde = self.crear('Borde')
        envejecer(borde, RETENCION_DIAS - 1)
        self.client.get('/api/notificaciones/')
        self.assertTrue(Notificacion.objects.filter(pk=borde.pk).exists())

    def test_historial_tambien_purga(self):
        vieja = self.crear('Vieja', archivada=True)
        envejecer(vieja, RETENCION_DIAS + 5)
        self.client.get('/api/notificaciones/historial/')
        self.assertFalse(Notificacion.objects.filter(pk=vieja.pk).exists())

    def test_purga_no_toca_otro_gym(self):
        """El barrido del viewset está acotado al gym del usuario."""
        ajena = self.crear('Ajena vieja', gym=self.otro_gym)
        envejecer(ajena, RETENCION_DIAS + 10)
        self.client.get('/api/notificaciones/')
        self.assertTrue(Notificacion.objects.filter(pk=ajena.pk).exists())

    def test_comando_limpiar_notificaciones(self):
        vieja = self.crear('Vieja')
        envejecer(vieja, RETENCION_DIAS + 1)
        reciente = self.crear('Reciente')
        out = StringIO()
        call_command('limpiar_notificaciones', stdout=out)
        self.assertFalse(Notificacion.objects.filter(pk=vieja.pk).exists())
        self.assertTrue(Notificacion.objects.filter(pk=reciente.pk).exists())
        self.assertIn('1 notificaciones eliminadas', out.getvalue())

    def test_comando_barre_todos_los_gyms(self):
        """A diferencia del viewset, el comando de cron es global."""
        ajena = self.crear('Ajena vieja', gym=self.otro_gym)
        envejecer(ajena, RETENCION_DIAS + 1)
        call_command('limpiar_notificaciones', stdout=StringIO())
        self.assertFalse(Notificacion.objects.filter(pk=ajena.pk).exists())


class NotificacionGeneradasPorElSistemaTests(NotificacionBase):
    """Las notificaciones nacen de eventos reales, no de un POST del cliente."""

    def test_alta_de_equipamiento_notifica(self):
        resp = self.client.post('/api/gyms/equipamiento/', {
            'nombre': 'Costal 100lb', 'categoria': 'impacto', 'cantidad': 4,
        })
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        noti = Notificacion.objects.get(gym=self.gym, tipo='inventario')
        self.assertIn('Costal 100lb', noti.mensaje)
        self.assertEqual(noti.link, '/equipamiento')

    def test_edicion_de_equipamiento_notifica(self):
        eq = Equipamiento.objects.create(gym=self.gym, nombre='Ring', categoria='infraestructura')
        self.client.patch(f'/api/gyms/equipamiento/{eq.id}/', {'cantidad': 2})
        self.assertTrue(
            Notificacion.objects.filter(tipo='inventario', mensaje__contains='actualizó').exists()
        )

    def test_baja_de_equipamiento_notifica(self):
        eq = Equipamiento.objects.create(gym=self.gym, nombre='Ring', categoria='infraestructura')
        self.client.delete(f'/api/gyms/equipamiento/{eq.id}/')
        self.assertTrue(
            Notificacion.objects.filter(tipo='inventario', mensaje__contains='eliminó').exists()
        )

    def test_notificacion_de_equipamiento_va_al_gym_correcto(self):
        self.client.post('/api/gyms/equipamiento/', {
            'nombre': 'Guantes', 'categoria': 'proteccion', 'cantidad': 10,
        })
        self.assertEqual(Notificacion.objects.filter(gym=self.otro_gym).count(), 0)
        self.assertEqual(Notificacion.objects.filter(gym=self.gym).count(), 1)

    def test_cliente_no_puede_inyectar_notificaciones(self):
        """gym/tipo/mensaje son read_only: un POST no puede fabricar avisos falsos."""
        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                self.client.post('/api/notificaciones/', {
                    'gym': self.otro_gym.id, 'tipo': 'pago_vencido', 'mensaje': 'Falso',
                })
        self.assertFalse(Notificacion.objects.filter(mensaje='Falso').exists())

    @unittest.expectedFailure
    def test_BUG_post_a_notificaciones_revienta_en_vez_de_devolver_400(self):
        """BUG (menor, robustez): NotificacionViewSet acepta POST (views.py:16) pero
        el serializer marca gym/tipo/mensaje como read_only (serializers.py:9).

        El POST pasa la validación con datos vacíos y muere en el INSERT con
        `IntegrityError: NOT NULL constraint failed: notificaciones.gym_id`,
        o sea un 500 en producción en lugar de un 400 limpio.
        No hay fuga de datos: la notificación nunca se crea. Arreglo: quitar 'post'
        de http_method_names, ya que todas las notificaciones las genera el backend.
        """
        resp = self.client.post('/api/notificaciones/', {
            'gym': self.otro_gym.id, 'tipo': 'pago_vencido', 'mensaje': 'Falso',
        })
        self.assertIn(
            resp.status_code,
            (status.HTTP_400_BAD_REQUEST, status.HTTP_405_METHOD_NOT_ALLOWED),
        )
