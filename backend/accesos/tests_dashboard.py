"""Datos que alimentan Dashboard y Reportes: /accesos/stats/, historial de accesos,
y los feeds de pagos/gastos que el frontend agrega para las gráficas.
"""

import zoneinfo
from datetime import datetime, date, timedelta

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework import status

from accesos.models import Acceso, MetodoAcceso
from gyms.models import Sucursal
from gyms.tests import BaseAPITestCase
from socios.models import Plan, Socio, Membresia, Pago, Gasto

TZ = zoneinfo.ZoneInfo(settings.TIME_ZONE)
HOY = date.today


def fechar(acceso, cuando):
    """`timestamp` es auto_now_add: se reescribe por UPDATE directo."""
    Acceso.objects.filter(pk=acceso.pk).update(timestamp=cuando)
    acceso.refresh_from_db()
    return acceso


def hora_local(dia, hora):
    return datetime(dia.year, dia.month, dia.day, hora, 0, tzinfo=TZ)


class StatsBase(BaseAPITestCase):
    def setUp(self):
        super().setUp()
        self.socio = Socio.objects.create(gym=self.gym, nombre='Ana', apellido='Lopez')

    def acceso(self, resultado='permitido', socio=None, sucursal=None, **kwargs):
        return Acceso.objects.create(
            socio=socio or self.socio, sucursal=sucursal or self.sucursal,
            resultado=resultado, metodo_usado='qr', **kwargs,
        )


class StatsEndpointTests(StatsBase):
    def test_stats_vacio_no_revienta(self):
        resp = self.client.get('/api/accesos/stats/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['accesos_hoy'], 0)
        self.assertEqual(resp.data['accesos_mes'], 0)
        self.assertEqual(resp.data['horarios_concurridos'], [])

    def test_cuenta_accesos_de_hoy(self):
        self.acceso()
        self.acceso()
        self.assertEqual(self.client.get('/api/accesos/stats/').data['accesos_hoy'], 2)

    def test_solo_cuenta_los_permitidos(self):
        self.acceso(resultado='permitido')
        self.acceso(resultado='denegado', motivo_denegado='sin_membresia')
        data = self.client.get('/api/accesos/stats/').data
        self.assertEqual(data['accesos_hoy'], 1)
        self.assertEqual(data['accesos_mes'], 1)

    def test_acceso_de_ayer_no_cuenta_como_hoy(self):
        ayer = self.acceso()
        fechar(ayer, hora_local(HOY() - timedelta(days=1), 10))
        self.assertEqual(self.client.get('/api/accesos/stats/').data['accesos_hoy'], 0)

    def test_acceso_del_mes_pasado_no_cuenta_en_el_mes(self):
        inicio_mes = HOY().replace(day=1)
        viejo = self.acceso()
        fechar(viejo, hora_local(inicio_mes - timedelta(days=1), 10))
        self.assertEqual(self.client.get('/api/accesos/stats/').data['accesos_mes'], 0)

    def test_accesos_del_mes_incluye_los_de_hoy(self):
        self.acceso()
        data = self.client.get('/api/accesos/stats/').data
        self.assertEqual(data['accesos_mes'], 1)
        self.assertEqual(data['accesos_hoy'], 1)

    def test_horarios_concurridos_agrupa_por_hora(self):
        for _ in range(3):
            fechar(self.acceso(), hora_local(HOY(), 19))
        fechar(self.acceso(), hora_local(HOY(), 7))
        por_hora = {h['hora']: h['total'] for h in self.client.get('/api/accesos/stats/').data['horarios_concurridos']}
        self.assertEqual(por_hora.get(19), 3)
        self.assertEqual(por_hora.get(7), 1)

    def test_horarios_concurridos_vienen_ordenados(self):
        for h in (20, 6, 13):
            fechar(self.acceso(), hora_local(HOY(), h))
        horas = [x['hora'] for x in self.client.get('/api/accesos/stats/').data['horarios_concurridos']]
        self.assertEqual(horas, sorted(horas))

    def test_horarios_ignora_denegados(self):
        fechar(self.acceso(resultado='denegado', motivo_denegado='sin_membresia'),
               hora_local(HOY(), 19))
        self.assertEqual(self.client.get('/api/accesos/stats/').data['horarios_concurridos'], [])

    def test_stats_scoped_al_gym(self):
        ajeno = Socio.objects.create(gym=self.otro_gym, nombre='Pedro', apellido='Ajeno')
        sucursal_ajena = Sucursal.objects.create(gym=self.otro_gym, nombre='Ajena')
        self.acceso(socio=ajeno, sucursal=sucursal_ajena)
        self.acceso()
        data = self.client.get('/api/accesos/stats/').data
        self.assertEqual(data['accesos_hoy'], 1)

    def test_stats_requiere_autenticacion(self):
        from rest_framework.test import APIClient
        resp = APIClient().get('/api/accesos/stats/')
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_recepcion_puede_ver_stats(self):
        from usuarios.models import Usuario
        recepcion = Usuario.objects.create_user(
            email='recep@round3.com', password='Passw0rd1', nombre='Recep',
            rol='recepcion', gym=self.gym,
        )
        self.authenticate(recepcion)
        self.assertEqual(self.client.get('/api/accesos/stats/').status_code, status.HTTP_200_OK)


class HistorialAccesosTests(StatsBase):
    """La bitácora que se ve en la pantalla de Accesos."""

    def test_orden_mas_reciente_primero(self):
        viejo = self.acceso()
        fechar(viejo, timezone.now() - timedelta(hours=5))
        self.acceso()
        resp = self.client.get('/api/accesos/')
        self.assertGreater(resp.data[0]['timestamp'], resp.data[1]['timestamp'])

    def test_incluye_permitidos_y_denegados(self):
        self.acceso(resultado='permitido')
        self.acceso(resultado='denegado', motivo_denegado='membresia_vencida')
        resultados = sorted(a['resultado'] for a in self.client.get('/api/accesos/').data)
        self.assertEqual(resultados, ['denegado', 'permitido'])

    def test_denegado_conserva_el_motivo(self):
        self.acceso(resultado='denegado', motivo_denegado='membresia_vencida')
        self.assertEqual(self.client.get('/api/accesos/').data[0]['motivo_denegado'], 'membresia_vencida')

    def test_historial_es_de_solo_lectura(self):
        acceso = self.acceso()
        self.assertEqual(
            self.client.patch(f'/api/accesos/{acceso.id}/', {'resultado': 'denegado'}).status_code,
            status.HTTP_405_METHOD_NOT_ALLOWED,
        )
        self.assertEqual(
            self.client.delete(f'/api/accesos/{acceso.id}/').status_code,
            status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    def test_checkin_deja_rastro_del_metodo(self):
        plan = Plan.objects.create(gym=self.gym, nombre='Mensual', tipo='mensual', precio=500)
        Membresia.objects.create(
            socio=self.socio, plan=plan, sucursal=self.sucursal,
            fecha_inicio=HOY(), fecha_fin=HOY() + timedelta(days=30), estado='activa',
        )
        MetodoAcceso.objects.create(socio=self.socio, tipo='rfid', token='RFID-1')
        self.client.post('/api/accesos/checkin/', {
            'token': 'RFID-1', 'sucursal_id': self.sucursal.id,
        })
        self.assertEqual(Acceso.objects.get(socio=self.socio).metodo_usado, 'rfid')

    def test_acceso_permitido_queda_ligado_a_la_membresia(self):
        plan = Plan.objects.create(gym=self.gym, nombre='Mensual', tipo='mensual', precio=500)
        membresia = Membresia.objects.create(
            socio=self.socio, plan=plan, sucursal=self.sucursal,
            fecha_inicio=HOY(), fecha_fin=HOY() + timedelta(days=30), estado='activa',
        )
        MetodoAcceso.objects.create(socio=self.socio, tipo='qr', token='QR-1')
        self.client.post('/api/accesos/checkin/', {
            'token': 'QR-1', 'sucursal_id': self.sucursal.id,
        })
        self.assertEqual(Acceso.objects.get(socio=self.socio).membresia_id, membresia.id)

    def test_acceso_denegado_no_queda_ligado_a_membresia(self):
        MetodoAcceso.objects.create(socio=self.socio, tipo='qr', token='QR-1')
        self.client.post('/api/accesos/checkin/', {
            'token': 'QR-1', 'sucursal_id': self.sucursal.id,
        })
        self.assertIsNone(Acceso.objects.get(socio=self.socio).membresia_id)


class CheckInEntradasMalformadasTests(StatsBase):
    """El kiosco es la superficie más expuesta: debe degradar limpio, no con un 500."""

    def test_sin_token(self):
        resp = self.client.post('/api/accesos/checkin/', {'sucursal_id': self.sucursal.id})
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_token_vacio(self):
        resp = self.client.post('/api/accesos/checkin/', {
            'token': '', 'sucursal_id': self.sucursal.id,
        })
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_BUG_checkin_acepta_sucursal_de_otro_gym(self):
        """BUG: CheckInView confía en el `sucursal_id` que manda el cliente sin
        comprobar que pertenezca al gym del usuario (accesos/views.py:67, 110-116).

        El acceso queda registrado contra la sucursal de otro negocio, así que
        ensucia la bitácora y los reportes por sucursal del gym ajeno.
        El QR sí está protegido (la consulta de MetodoAcceso filtra por gym);
        lo que falta es la misma comprobación sobre la sucursal.
        """
        MetodoAcceso.objects.create(socio=self.socio, tipo='qr', token='QR-1')
        sucursal_ajena = Sucursal.objects.create(gym=self.otro_gym, nombre='Ajena')
        self.client.post('/api/accesos/checkin/', {
            'token': 'QR-1', 'sucursal_id': sucursal_ajena.id,
        })
        self.assertFalse(Acceso.objects.filter(sucursal=sucursal_ajena).exists())

    def test_BUG_checkin_sin_sucursal_revienta_en_vez_de_devolver_400(self):
        """BUG (menor, robustez): CheckInView crea el Acceso con
        `sucursal_id=request.data.get('sucursal_id')` sin validarlo
        (accesos/views.py:67, 90-96 y 110-116), pero Acceso.sucursal es NOT NULL
        (accesos/models.py:42).

        Si el kiosco manda el check-in sin sucursal —por ejemplo cuando el gym
        todavía no tiene ninguna dada de alta y el selector de CheckIn.jsx queda
        vacío— la petición muere con
        `IntegrityError: NOT NULL constraint failed: accesos.sucursal_id`.
        Arreglo: validar sucursal_id contra las sucursales del gym antes de registrar.
        """
        MetodoAcceso.objects.create(socio=self.socio, tipo='qr', token='QR-1')
        resp = self.client.post('/api/accesos/checkin/', {'token': 'QR-1'})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)


class DashboardSociosFeedTests(BaseAPITestCase):
    """Dashboard.jsx cuenta socios y membresías activas desde /api/socios/."""

    def setUp(self):
        super().setUp()
        self.plan = Plan.objects.create(
            gym=self.gym, nombre='Mensual', tipo='mensual', precio=500, duracion_dias=30,
        )

    def _socio(self, nombre, estado=None, activo=True, fecha_fin=None):
        socio = Socio.objects.create(gym=self.gym, nombre=nombre, apellido='T', activo=activo)
        if estado:
            Membresia.objects.create(
                socio=socio, plan=self.plan, sucursal=self.sucursal,
                fecha_inicio=HOY(), fecha_fin=fecha_fin, estado=estado,
            )
        return socio

    def test_conteo_de_altas_y_bajas(self):
        self._socio('A', estado='activa', fecha_fin=HOY() + timedelta(days=30))
        self._socio('B', estado='vencida', fecha_fin=HOY() - timedelta(days=1))
        self._socio('C', activo=False)
        data = self.client.get('/api/socios/').data
        self.assertEqual(len(data), 3)
        self.assertEqual(sum(1 for s in data if s['activo']), 2)
        self.assertEqual(sum(1 for s in data if not s['activo']), 1)

    def test_conteo_de_membresias_activas(self):
        self._socio('A', estado='activa', fecha_fin=HOY() + timedelta(days=30))
        self._socio('B', estado='activa', fecha_fin=HOY() + timedelta(days=10))
        self._socio('C', estado='vencida', fecha_fin=HOY() - timedelta(days=1))
        self._socio('D')
        data = self.client.get('/api/socios/').data
        con_plan = [s for s in data if s['membresia_activa']]
        self.assertEqual(len(con_plan), 2)

    def test_socio_trae_su_codigo_de_acceso(self):
        resp = self.client.post('/api/socios/', {'nombre': 'Nuevo', 'apellido': 'Socio'})
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        fila = next(s for s in self.client.get('/api/socios/').data if s['id'] == resp.data['id'])
        self.assertTrue(fila['codigo_acceso'].startswith('R3B-QR-'))

    def test_codigo_de_acceso_desactivado_no_se_publica(self):
        socio = self._socio('Ana')
        MetodoAcceso.objects.create(socio=socio, tipo='qr', token='QR-OFF', activo=False)
        fila = next(s for s in self.client.get('/api/socios/').data if s['id'] == socio.id)
        self.assertIsNone(fila['codigo_acceso'])


class ReportesFeedTests(BaseAPITestCase):
    """Reportes.jsx cruza /socios/pagos/ contra /socios/gastos/ para el corte del mes."""

    def setUp(self):
        super().setUp()
        self.socio = Socio.objects.create(gym=self.gym, nombre='Ana', apellido='Lopez')
        self.plan = Plan.objects.create(gym=self.gym, nombre='Mensual', tipo='mensual', precio=500)
        self.membresia = Membresia.objects.create(
            socio=self.socio, plan=self.plan, sucursal=self.sucursal,
            fecha_inicio=HOY(), estado='activa',
        )

    def test_pago_trae_socio_plan_y_cobrador(self):
        resp = self.client.post('/api/socios/pagos/', {
            'membresia': self.membresia.id, 'monto': '500.00', 'metodo': 'efectivo',
        })
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        fila = self.client.get('/api/socios/pagos/').data[0]
        self.assertEqual(fila['socio_nombre'], 'Ana Lopez')
        self.assertEqual(fila['plan_nombre'], 'Mensual')
        self.assertEqual(fila['registrado_por_nombre'], 'Admin')

    def test_ingresos_por_metodo_de_pago(self):
        for metodo, monto in (('efectivo', 500), ('tarjeta', 300), ('transferencia', 200)):
            Pago.objects.create(membresia=self.membresia, monto=monto, metodo=metodo)
        pagos = self.client.get('/api/socios/pagos/').data
        por_metodo = {p['metodo']: p['monto'] for p in pagos}
        self.assertEqual(sorted(por_metodo), ['efectivo', 'tarjeta', 'transferencia'])
        self.assertEqual(sum(float(p['monto']) for p in pagos), 1000.0)

    def test_metodo_de_pago_invalido_es_rechazado(self):
        resp = self.client.post('/api/socios/pagos/', {
            'membresia': self.membresia.id, 'monto': '500.00', 'metodo': 'bitcoin',
        })
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_gastos_por_categoria(self):
        for categoria, monto in (('renta', 8000), ('nomina', 12000), ('servicios', 1500)):
            Gasto.objects.create(gym=self.gym, categoria=categoria, descripcion=categoria,
                                 monto=monto, fecha=HOY())
        gastos = self.client.get('/api/socios/gastos/').data
        self.assertEqual(len(gastos), 3)
        self.assertEqual(sum(float(g['monto']) for g in gastos), 21500.0)

    def test_categoria_de_gasto_invalida_es_rechazada(self):
        resp = self.client.post('/api/socios/gastos/', {
            'categoria': 'criptomonedas', 'descripcion': 'X', 'monto': '1.00',
            'fecha': HOY().isoformat(),
        })
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_utilidad_del_periodo(self):
        Pago.objects.create(membresia=self.membresia, monto=10000, metodo='efectivo')
        Gasto.objects.create(gym=self.gym, categoria='renta', descripcion='Renta',
                             monto=8000, fecha=HOY())
        ingresos = sum(float(p['monto']) for p in self.client.get('/api/socios/pagos/').data)
        egresos = sum(float(g['monto']) for g in self.client.get('/api/socios/gastos/').data)
        self.assertEqual(ingresos - egresos, 2000.0)

    def test_pagos_de_otro_gym_no_contaminan_el_reporte(self):
        sucursal_ajena = Sucursal.objects.create(gym=self.otro_gym, nombre='Ajena')
        plan_ajeno = Plan.objects.create(gym=self.otro_gym, nombre='Ajeno', tipo='mensual', precio=999)
        ajeno = Socio.objects.create(gym=self.otro_gym, nombre='Pedro', apellido='Ajeno')
        membresia_ajena = Membresia.objects.create(
            socio=ajeno, plan=plan_ajeno, sucursal=sucursal_ajena,
            fecha_inicio=HOY(), estado='activa',
        )
        Pago.objects.create(membresia=membresia_ajena, monto=9999, metodo='efectivo')
        Pago.objects.create(membresia=self.membresia, monto=500, metodo='efectivo')
        pagos = self.client.get('/api/socios/pagos/').data
        self.assertEqual(len(pagos), 1)
        self.assertEqual(float(pagos[0]['monto']), 500.0)
