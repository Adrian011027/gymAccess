"""El listado de socios no debe crecer en consultas con cada socio.

Antes hacía ~5 consultas por socio (membresía vigente, la más reciente, sus planes y
el consentimiento): 252 para 50 socios y 1,002 para 200. Ahora las precarga, y estas
pruebas fijan que el número de consultas no dependa de cuántos socios haya.
"""

from datetime import timedelta
from decimal import Decimal

from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework import status

from accesos.models import MetodoAcceso
from gyms.tests import BaseAPITestCase
from legal.models import ConsentimientoSocio, DocumentoLegal
from socios.models import Membresia, Plan, Socio

HOY = timezone.localdate


class ListadoSociosConsultasTests(BaseAPITestCase):
    def setUp(self):
        super().setUp()
        self.plan = Plan.objects.create(
            gym=self.gym, nombre='Mensual', tipo='mensual', precio=Decimal('500'), duracion_dias=30,
        )
        self.aviso = DocumentoLegal.objects.create(
            gym=self.gym, tipo=DocumentoLegal.AVISO_PRIVACIDAD, version='1.0',
            titulo='Aviso', contenido='Texto',
        )
        self.numero = 1000

    def crear_socios(self, cuantos):
        for _ in range(cuantos):
            self.numero += 1
            socio = Socio.objects.create(
                gym=self.gym, nombre=f'Socio{self.numero}', apellido='Prueba',
                numero_socio=self.numero, sucursal=self.sucursal,
            )
            MetodoAcceso.objects.create(socio=socio, tipo='qr', token=f'TOKEN-{self.numero}')
            Membresia.objects.create(
                socio=socio, plan=self.plan, sucursal=self.sucursal,
                fecha_inicio=HOY() - timedelta(days=40), fecha_fin=HOY() - timedelta(days=10),
                estado='vencida',
            )
            Membresia.objects.create(
                socio=socio, plan=self.plan, sucursal=self.sucursal,
                fecha_inicio=HOY(), fecha_fin=HOY() + timedelta(days=30), estado='activa',
            )
            ConsentimientoSocio.objects.create(socio=socio, documento=self.aviso)

    def listar(self):
        with CaptureQueriesContext(connection) as consultas:
            resp = self.client.get('/api/socios/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        return len(consultas.captured_queries), resp.data

    def test_las_consultas_no_crecen_con_los_socios(self):
        self.crear_socios(2)
        con_pocos, _ = self.listar()

        self.crear_socios(20)
        con_muchos, datos = self.listar()

        self.assertEqual(len(datos), 22)
        self.assertEqual(con_pocos, con_muchos)

    def test_sigue_trayendo_vigente_reciente_y_consentimiento(self):
        self.crear_socios(1)

        _, datos = self.listar()
        socio = datos[0]

        self.assertEqual(socio['membresia_activa']['fecha_fin'], HOY() + timedelta(days=30))
        self.assertEqual(socio['membresia_reciente']['fecha_inicio'], HOY())
        self.assertEqual(socio['consentimiento']['version'], '1.0')
        self.assertTrue(socio['codigo_acceso'].startswith('TOKEN-'))


class EsVigenteIgualQueVigentesTests(BaseAPITestCase):
    """`es_vigente` (en memoria) y `vigentes()` (en la base) deben decir lo mismo.

    El listado usa la primera y el check-in la segunda: si divergen, la pantalla dice
    "al corriente" a alguien que la puerta rechaza.
    """

    def test_coinciden_en_cada_caso(self):
        plan = Plan.objects.create(gym=self.gym, nombre='Plan', tipo='mensual', precio=Decimal('1'))
        socio = Socio.objects.create(gym=self.gym, nombre='Ana', apellido='Lopez')
        dia = timedelta(days=1)
        casos = [
            {'estado': 'activa', 'fecha_inicio': HOY(), 'fecha_fin': HOY()},
            {'estado': 'activa', 'fecha_inicio': HOY() - 10 * dia, 'fecha_fin': HOY() - dia},
            {'estado': 'activa', 'fecha_inicio': HOY() + dia, 'fecha_fin': HOY() + 30 * dia},
            {'estado': 'activa', 'fecha_inicio': HOY(), 'fecha_fin': None},
            {'estado': 'vencida', 'fecha_inicio': HOY(), 'fecha_fin': HOY() + 30 * dia},
            {'estado': 'pendiente_pago', 'fecha_inicio': HOY(), 'fecha_fin': HOY() + 30 * dia},
            {'estado': 'activa', 'fecha_inicio': HOY(), 'fecha_fin': HOY() + dia, 'clases_restantes': 0},
            {'estado': 'activa', 'fecha_inicio': HOY(), 'fecha_fin': HOY() + dia, 'clases_restantes': 3},
        ]
        for datos in casos:
            membresia = Membresia.objects.create(
                socio=socio, plan=plan, sucursal=self.sucursal, **datos,
            )
            with self.subTest(**{k: str(v) for k, v in datos.items()}):
                self.assertEqual(
                    membresia.es_vigente(),
                    Membresia.objects.vigentes().filter(id=membresia.id).exists(),
                )
