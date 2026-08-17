"""El comando que corre en cron todas las noches: marcar_membresias_vencidas.

Estaba al 0% de cobertura. Importa porque es lo único que mueve el estado de una
membresía a 'vencida' cuando pasa su fecha, y porque convive con la regla de fecha fija
de cobro: si marcara de más, un socio al corriente amanecería vencido; si marcara de
menos, los filtros de la pantalla de Pagos dejarían de cuadrar.
"""

from datetime import date, timedelta
from io import StringIO

from django.core.management import call_command

from gyms.tests import BaseAPITestCase
from socios.models import DIAS_GRACIA_REINSCRIPCION, Plan, Socio, Membresia

HOY = date.today


class MarcarMembresiasVencidasTests(BaseAPITestCase):
    def setUp(self):
        super().setUp()
        self.plan = Plan.objects.create(
            gym=self.gym, nombre='Mensual', tipo='mensual', precio=500, duracion_dias=30,
        )

    def crear(self, nombre, estado, fecha_fin, gym=None):
        socio = Socio.objects.create(
            gym=gym or self.gym, nombre=nombre, apellido='Test',
        )
        return Membresia.objects.create(
            socio=socio, plan=self.plan, sucursal=self.sucursal,
            fecha_inicio=HOY() - timedelta(days=60),
            fecha_fin=fecha_fin, estado=estado,
        )

    def correr(self, *args):
        salida = StringIO()
        call_command('marcar_membresias_vencidas', *args, stdout=salida)
        return salida.getvalue()

    def test_marca_la_activa_con_fecha_pasada(self):
        m = self.crear('Vencido', 'activa', HOY() - timedelta(days=1))
        self.correr()
        m.refresh_from_db()
        self.assertEqual(m.estado, 'vencida')

    def test_no_toca_la_que_vence_hoy(self):
        """Frontera: el último día todavía cuenta como vigente."""
        m = self.crear('Hoy', 'activa', HOY())
        self.correr()
        m.refresh_from_db()
        self.assertEqual(m.estado, 'activa')

    def test_no_toca_la_vigente(self):
        m = self.crear('Vigente', 'activa', HOY() + timedelta(days=15))
        self.correr()
        m.refresh_from_db()
        self.assertEqual(m.estado, 'activa')

    def test_no_toca_las_perpetuas(self):
        """Sin fecha_fin no hay nada que vencer; marcarlas dejaría fuera a un socio
        con plan sin vencimiento."""
        m = self.crear('Libre', 'activa', None)
        self.correr()
        m.refresh_from_db()
        self.assertEqual(m.estado, 'activa')

    def test_no_reactiva_ni_pisa_otros_estados(self):
        susp = self.crear('Susp', 'suspendida', HOY() - timedelta(days=5))
        pend = self.crear('Pend', 'pendiente_pago', HOY() - timedelta(days=5))
        self.correr()
        susp.refresh_from_db()
        pend.refresh_from_db()
        self.assertEqual(susp.estado, 'suspendida')
        self.assertEqual(pend.estado, 'pendiente_pago')

    def test_es_idempotente(self):
        m = self.crear('Vencido', 'activa', HOY() - timedelta(days=1))
        self.correr()
        self.correr()
        m.refresh_from_db()
        self.assertEqual(m.estado, 'vencida')

    def test_dry_run_no_escribe(self):
        m = self.crear('Vencido', 'activa', HOY() - timedelta(days=1))
        salida = self.correr('--dry-run')
        m.refresh_from_db()
        self.assertEqual(m.estado, 'activa', 'dry-run no debe tocar la base')
        self.assertIn('Vencido', salida)
        self.assertIn('dry-run', salida)

    def test_reporta_el_total(self):
        for i in range(3):
            self.crear(f'V{i}', 'activa', HOY() - timedelta(days=1))
        self.assertIn('3', self.correr())

    def test_atraviesa_todos_los_gyms(self):
        """El comando corre en cron para toda la instalación, no por gym."""
        ajeno = self.crear('Ajeno', 'activa', HOY() - timedelta(days=1), gym=self.otro_gym)
        propio = self.crear('Propio', 'activa', HOY() - timedelta(days=1))
        self.correr()
        ajeno.refresh_from_db()
        propio.refresh_from_db()
        self.assertEqual(ajeno.estado, 'vencida')
        self.assertEqual(propio.estado, 'vencida')

    def test_sin_nada_que_marcar_no_falla(self):
        self.assertIn('0', self.correr())

    def test_marcada_por_el_cron_se_renueva_conservando_su_dia_de_corte(self):
        """El cruce que importa: el cron la marca vencida de madrugada y el socio paga
        ese mismo día. Debe conservar su ancla, no reiniciarse en hoy."""
        corte = HOY() - timedelta(days=2)
        m = self.crear('Puntual', 'activa', corte)
        self.correr()
        m.refresh_from_db()
        self.assertEqual(m.estado, 'vencida')

        m.renovar()
        self.assertEqual(m.estado, 'activa')
        self.assertEqual(m.fecha_fin.day, corte.day, 'el día de corte no se mueve')

    def test_moroso_de_meses_marcado_por_el_cron_se_reinscribe(self):
        corte = HOY() - timedelta(days=DIAS_GRACIA_REINSCRIPCION + 10)
        m = self.crear('Moroso', 'activa', corte)
        self.correr()
        m.refresh_from_db()

        m.renovar()
        self.assertEqual(m.fecha_inicio, HOY())
        self.assertEqual(m.fecha_fin.day, HOY().day)
