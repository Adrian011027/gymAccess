"""El borrado de un socio no destruye nada.

Un DELETE real arrastraba por cascada `Membresia` -> `Pago` (que el CFF art. 30 manda
conservar 5 años), `ConsentimientoSocio` (la evidencia de la LFPDPPP) y `Acceso` (la
bitácora del local). Estos tests fijan que eso ya no puede volver a pasar: si alguien
quita el `perform_destroy` y deja el de DRF, fallan.
"""

from datetime import timedelta

from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from accesos.models import Acceso, MetodoAcceso
from gyms.models import Gym, Sucursal
from socios.models import Membresia, Pago, Plan, Socio
from usuarios.models import Usuario


class BorradoLogicoSocioTests(APITestCase):
    def setUp(self):
        self.gym = Gym.objects.create(nombre='Gym', activo=True)
        self.suc = Sucursal.objects.create(gym=self.gym, nombre='Centro', activa=True)
        self.admin = Usuario.objects.create_user(
            email='admin@t.com', password='Xk92mLp4vQ', nombre='Admin',
            rol='admin', gym=self.gym,
        )
        self.recep = Usuario.objects.create_user(
            email='recep@t.com', password='Xk92mLp4vQ', nombre='Recep',
            rol='recepcion', gym=self.gym, sucursal=self.suc,
        )
        self.plan = Plan.objects.create(
            gym=self.gym, nombre='Mensual', precio=500, duracion_dias=30, activo=True,
        )
        hoy = timezone.localdate()
        self.socio = Socio.objects.create(
            gym=self.gym, sucursal=self.suc, nombre='Ana', apellido='Test',
        )
        self.metodo = MetodoAcceso.objects.create(
            socio=self.socio, tipo='qr', token='tok-ana', activo=True,
        )
        self.membresia = Membresia.objects.create(
            socio=self.socio, plan=self.plan, sucursal=self.suc,
            fecha_inicio=hoy, fecha_fin=hoy + timedelta(days=30), estado='activa',
        )
        self.pago = Pago.objects.create(
            membresia=self.membresia, monto=500, metodo='efectivo',
        )
        self.acceso = Acceso.objects.create(
            socio=self.socio, sucursal=self.suc, resultado='permitido',
        )

    def borrar(self, quien=None):
        self.client.force_authenticate(quien or self.admin)
        return self.client.delete(f'/api/socios/{self.socio.id}/')

    # --- lo que NO se debe destruir -----------------------------------------

    def test_la_fila_del_socio_sobrevive(self):
        self.assertEqual(self.borrar().status_code, status.HTTP_204_NO_CONTENT)
        self.assertTrue(Socio.objects.filter(id=self.socio.id).exists())

    def test_los_pagos_sobreviven(self):
        """Obligación fiscal: cinco años. Un DELETE en cascada se los llevaba."""
        self.borrar()
        self.assertTrue(Pago.objects.filter(id=self.pago.id).exists())

    def test_la_membresia_sobrevive(self):
        self.borrar()
        self.assertTrue(Membresia.objects.filter(id=self.membresia.id).exists())

    def test_la_bitacora_de_accesos_sobrevive(self):
        """Es registro de quién entró al local, no un dato de contacto."""
        self.borrar()
        self.assertTrue(Acceso.objects.filter(id=self.acceso.id).exists())

    # --- lo que sí debe cambiar ---------------------------------------------

    def test_queda_marcado_y_con_responsable(self):
        self.borrar()
        self.socio.refresh_from_db()
        self.assertIsNotNone(self.socio.eliminado_en)
        self.assertEqual(self.socio.eliminado_por, self.admin)
        self.assertFalse(self.socio.activo)

    def test_el_qr_deja_de_abrir(self):
        self.borrar()
        self.metodo.refresh_from_db()
        self.assertFalse(self.metodo.activo)

    def test_desaparece_del_listado(self):
        self.borrar()
        self.client.force_authenticate(self.admin)
        ids = [s['id'] for s in self.client.get('/api/socios/').data]
        self.assertNotIn(self.socio.id, ids)

    def test_no_lo_encuentra_ni_la_busqueda(self):
        """La búsqueda cruza sucursales, pero no resucita a un eliminado."""
        self.borrar()
        self.client.force_authenticate(self.admin)
        resp = self.client.get('/api/socios/?buscar=Ana')
        self.assertEqual([s['id'] for s in resp.data], [])

    def test_su_membresia_sale_de_por_cobrar(self):
        """Si no, recepción ve una deuda de alguien que ya no está en el listado."""
        self.borrar()
        self.client.force_authenticate(self.admin)
        ids = [m['id'] for m in self.client.get('/api/socios/membresias/').data]
        self.assertNotIn(self.membresia.id, ids)

    def test_el_check_in_ya_no_lo_encuentra(self):
        self.borrar()
        self.client.force_authenticate(self.recep)
        resp = self.client.get('/api/accesos/buscar-socio/?q=Ana')
        self.assertEqual(len(resp.data), 0)

    # --- reversibilidad ------------------------------------------------------

    def test_el_admin_puede_restaurarlo(self):
        self.borrar()
        self.client.force_authenticate(self.admin)
        resp = self.client.post(f'/api/socios/{self.socio.id}/restaurar/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.socio.refresh_from_db()
        self.metodo.refresh_from_db()
        self.assertIsNone(self.socio.eliminado_en)
        self.assertTrue(self.socio.activo)
        self.assertTrue(self.metodo.activo)

    def test_recepcion_no_puede_restaurar(self):
        self.borrar()
        self.client.force_authenticate(self.recep)
        resp = self.client.post(f'/api/socios/{self.socio.id}/restaurar/')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_solo_el_admin_ve_las_bajas(self):
        self.borrar()
        self.client.force_authenticate(self.admin)
        ids = [s['id'] for s in self.client.get('/api/socios/?incluir_eliminados=1').data]
        self.assertIn(self.socio.id, ids)

        self.client.force_authenticate(self.recep)
        ids = [s['id'] for s in self.client.get('/api/socios/?incluir_eliminados=1').data]
        self.assertNotIn(self.socio.id, ids)

    def test_recepcion_no_puede_dar_de_baja(self):
        """Es del dueño, no del mostrador. Y el botón oculto no basta: se comprueba
        contra el endpoint, que es por donde entraria un DELETE hecho a mano."""
        resp = self.borrar(self.recep)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self.socio.refresh_from_db()
        self.assertIsNone(self.socio.eliminado_en)

    def test_no_se_puede_borrar_dos_veces(self):
        """404 y no 400: para `destroy` el socio ya dado de baja no existe, porque
        `get_queryset` lo filtra antes de llegar a `perform_destroy`."""
        self.borrar()
        self.assertEqual(self.borrar().status_code, status.HTTP_404_NOT_FOUND)
