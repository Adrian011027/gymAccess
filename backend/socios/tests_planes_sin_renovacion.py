"""Plan semanal (5 clases o 7 días) y visitas: planes que no se renuevan.

Lo que fijan estas pruebas:
- el semanal se acaba con la última clase o al séptimo día, lo que ocurra primero;
- cuando un plan sin renovación se acaba no es un cobro atrasado: ni "Por cobrar",
  ni aviso de pago vencido, solo "sin membresía activa";
- quien ya estuvo registrado no se registra de nuevo: paga y se le activa.
"""

from datetime import timedelta
from decimal import Decimal

from django.utils import timezone
from rest_framework import status

from accesos.models import Acceso, MetodoAcceso
from gyms.tests import BaseAPITestCase
from notificaciones.models import Notificacion
from socios.models import Membresia, Plan, Socio

HOY = timezone.localdate


class PlanesBase(BaseAPITestCase):
    def setUp(self):
        super().setUp()
        self.semanal = Plan.objects.create(
            gym=self.gym, nombre='Semanal', tipo='semanal', precio=Decimal('200'),
            duracion_dias=7, num_clases=5,
        )
        self.mensual = Plan.objects.create(
            gym=self.gym, nombre='Mensual', tipo='mensual', precio=Decimal('500'),
            duracion_dias=30,
        )
        self.visita = Plan.objects.create(
            gym=self.gym, nombre='Visita', tipo='visita', precio=Decimal('80'), duracion_dias=1,
        )
        self.socio = Socio.objects.create(
            gym=self.gym, nombre='Ana', apellido='Lopez', numero_socio=1001,
            sucursal=self.sucursal,
        )
        MetodoAcceso.objects.create(socio=self.socio, tipo='qr', token='TOKEN-ANA')

    def membresia(self, plan, inicio=None, **extra):
        inicio = inicio or HOY()
        datos = {
            'socio': self.socio, 'plan': plan, 'sucursal': self.sucursal,
            'fecha_inicio': inicio, 'fecha_fin': plan.fecha_fin_desde(inicio),
            'clases_restantes': plan.num_clases, 'estado': 'activa',
        }
        datos.update(extra)
        return Membresia.objects.create(**datos)

    def checkin(self):
        return self.client.post('/api/accesos/checkin/', {
            'token': 'TOKEN-ANA', 'sucursal_id': self.sucursal.id,
        })


class PlanSemanalConfiguracionTests(PlanesBase):
    def test_sin_dias_ni_clases_queda_en_7_dias_y_5_clases(self):
        resp = self.client.post('/api/socios/planes/', {
            'nombre': 'Semana', 'tipo': 'semanal', 'precio': '250',
        }, format='json')

        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        self.assertEqual(resp.data['duracion_dias'], 7)
        self.assertEqual(resp.data['num_clases'], 5)

    def test_no_puede_durar_mas_de_7_dias(self):
        resp = self.client.post('/api/socios/planes/', {
            'nombre': 'Semana larga', 'tipo': 'semanal', 'precio': '250', 'duracion_dias': 10,
        }, format='json')

        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('duracion_dias', resp.data)


class PlanSemanalVigenciaTests(PlanesBase):
    def test_el_septimo_dia_todavia_entra(self):
        self.membresia(self.semanal, inicio=HOY() - timedelta(days=6))

        self.assertTrue(Membresia.objects.vigentes().filter(socio=self.socio).exists())

    def test_el_octavo_dia_ya_no(self):
        self.membresia(self.semanal, inicio=HOY() - timedelta(days=7))

        self.assertFalse(Membresia.objects.vigentes().filter(socio=self.socio).exists())

    def test_cada_entrada_gasta_una_clase(self):
        m = self.membresia(self.semanal)

        resp = self.checkin()

        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.assertEqual(resp.data['clases_restantes'], 4)
        m.refresh_from_db()
        self.assertEqual(m.clases_restantes, 4)

    def test_con_la_ultima_clase_se_acaba_aunque_le_queden_dias(self):
        self.membresia(self.semanal, clases_restantes=1)

        self.assertEqual(self.checkin().status_code, status.HTTP_200_OK)

        self.assertFalse(Membresia.objects.vigentes().filter(socio=self.socio).exists())

    def test_plan_sin_clases_contadas_no_descuenta_nada(self):
        m = self.membresia(self.mensual)

        resp = self.checkin()

        self.assertIsNone(resp.data['clases_restantes'])
        m.refresh_from_db()
        self.assertIsNone(m.clases_restantes)


class SinRenovacionNoEsCobroTests(PlanesBase):
    def test_semanal_acabado_se_niega_como_sin_membresia_y_no_avisa_pago_vencido(self):
        self.membresia(self.semanal, inicio=HOY() - timedelta(days=10))

        resp = self.checkin()

        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(resp.data['motivo'], 'no tiene membresía activa')
        self.assertEqual(Acceso.objects.get(socio=self.socio).motivo_denegado, 'sin_membresia')
        self.assertFalse(Notificacion.objects.filter(tipo='pago_vencido').exists())

    def test_mensual_vencido_sigue_siendo_cobro_atrasado(self):
        self.membresia(self.mensual, inicio=HOY() - timedelta(days=40))

        resp = self.checkin()

        self.assertEqual(Acceso.objects.get(socio=self.socio).motivo_denegado, 'membresia_vencida')
        self.assertEqual(resp.data['motivo'], 'membresía no activa')
        self.assertTrue(Notificacion.objects.filter(tipo='pago_vencido').exists())

    def test_membresias_dicen_si_su_plan_se_renueva(self):
        semanal = self.membresia(self.semanal, inicio=HOY() - timedelta(days=10))
        otro = Socio.objects.create(gym=self.gym, nombre='Beto', apellido='Ruiz', sucursal=self.sucursal)
        mensual = Membresia.objects.create(
            socio=otro, plan=self.mensual, sucursal=self.sucursal,
            fecha_inicio=HOY() - timedelta(days=40), fecha_fin=HOY() - timedelta(days=10),
            estado='activa',
        )

        datos = {m['id']: m for m in self.client.get('/api/socios/membresias/').data}

        self.assertFalse(datos[semanal.id]['plan_renovable'])
        self.assertTrue(datos[mensual.id]['plan_renovable'])

    def test_el_socio_trae_que_su_ultimo_plan_no_se_renueva(self):
        self.membresia(self.semanal, inicio=HOY() - timedelta(days=10))

        socio = next(s for s in self.client.get('/api/socios/').data if s['id'] == self.socio.id)

        self.assertIsNone(socio['membresia_activa'])
        self.assertFalse(socio['membresia_reciente']['renovable'])


class VolverAPagarTests(PlanesBase):
    def test_pagar_reactiva_el_semanal_con_dias_y_clases_completos(self):
        m = self.membresia(self.semanal, inicio=HOY() - timedelta(days=10), clases_restantes=0)

        resp = self.client.post('/api/socios/pagos/', {
            'membresia': m.id, 'monto': '200', 'metodo': 'efectivo',
        })

        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        m.refresh_from_db()
        self.assertEqual(m.fecha_inicio, HOY())
        self.assertEqual(m.fecha_fin, HOY() + timedelta(days=6))
        self.assertEqual(m.clases_restantes, 5)
        self.assertTrue(Membresia.objects.vigentes().filter(socio=self.socio).exists())
        self.assertEqual(Socio.objects.count(), 1)

    def test_pagar_una_visita_vale_solo_por_hoy(self):
        m = self.membresia(self.visita, inicio=HOY() - timedelta(days=3))

        self.client.post('/api/socios/pagos/', {'membresia': m.id, 'monto': '80', 'metodo': 'efectivo'})

        m.refresh_from_db()
        self.assertEqual(m.fecha_fin, HOY())

    def test_alta_de_semanal_pone_las_clases_y_los_7_dias_del_servidor(self):
        resp = self.client.post('/api/socios/membresias/', {
            'socio': self.socio.id, 'plan': self.semanal.id, 'sucursal': self.sucursal.id,
            'fecha_inicio': str(HOY()), 'fecha_fin': str(HOY() + timedelta(days=7)),
            'estado': 'activa',
        }, format='json')

        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        self.assertEqual(resp.data['clases_restantes'], 5)
        self.assertEqual(resp.data['fecha_fin'], str(HOY() + timedelta(days=6)))


class CambiarDePlanTests(PlanesBase):
    """Cambiar el plan de una membresía aplica las reglas del nuevo sin regalar nada."""

    def cambiar(self, membresia, plan):
        resp = self.client.patch(
            f'/api/socios/membresias/{membresia.id}/', {'plan': plan.id}, format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        membresia.refresh_from_db()
        return membresia

    def test_mensual_activo_a_semanal_toma_clases_y_no_pasa_de_lo_pagado(self):
        """El caso real: mensual del 20 al 19, cambiado a semanal a mitad de mes."""
        m = self.membresia(self.mensual, inicio=HOY() - timedelta(days=25))
        fin_pagado = m.fecha_fin

        m = self.cambiar(m, self.semanal)

        self.assertEqual(m.clases_restantes, 5)
        self.assertEqual(m.fecha_fin, min(fin_pagado, HOY() + timedelta(days=6)))

    def test_a_semanal_con_mucho_mes_por_delante_queda_en_7_dias(self):
        m = self.membresia(self.mensual, inicio=HOY() - timedelta(days=2))

        m = self.cambiar(m, self.semanal)

        self.assertEqual(m.fecha_fin, HOY() + timedelta(days=6))

    def test_nunca_alarga_la_fecha_pagada(self):
        m = self.membresia(self.mensual, inicio=HOY() - timedelta(days=28))
        fin_pagado = m.fecha_fin

        m = self.cambiar(m, self.semanal)

        self.assertEqual(m.fecha_fin, fin_pagado)

    def test_no_sube_las_clases_que_ya_le_quedaban(self):
        paquete = Plan.objects.create(
            gym=self.gym, nombre='10 clases', tipo='clases', precio=Decimal('800'), num_clases=10,
        )
        m = self.membresia(self.semanal, clases_restantes=2)

        m = self.cambiar(m, paquete)

        self.assertEqual(m.clases_restantes, 2)

    def test_a_un_plan_sin_clases_se_quita_el_tope(self):
        m = self.membresia(self.semanal, clases_restantes=3)

        m = self.cambiar(m, self.mensual)

        self.assertIsNone(m.clases_restantes)

    def test_editar_sin_cambiar_de_plan_no_toca_clases_ni_fechas(self):
        m = self.membresia(self.semanal, clases_restantes=3)
        fin = m.fecha_fin

        self.client.patch(f'/api/socios/membresias/{m.id}/', {'estado': 'activa'}, format='json')

        m.refresh_from_db()
        self.assertEqual((m.clases_restantes, m.fecha_fin), (3, fin))


class VisitaDeQuienYaVinoTests(PlanesBase):
    def registrar(self, **extra):
        cuerpo = {'plan': self.visita.id, 'sucursal': self.sucursal.id, 'metodo': 'efectivo'}
        cuerpo.update(extra)
        return self.client.post('/api/accesos/visita/', cuerpo, format='json')

    def test_no_crea_otra_persona_y_le_cobra_sobre_su_ficha(self):
        self.membresia(self.visita, inicio=HOY() - timedelta(days=5))

        resp = self.registrar(socio=self.socio.id)

        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        self.assertEqual(resp.data['socio_id'], self.socio.id)
        self.assertEqual(Socio.objects.count(), 1)
        self.assertTrue(Membresia.objects.vigentes().filter(socio=self.socio).exists())
        self.assertTrue(Acceso.objects.filter(socio=self.socio, resultado='permitido').exists())

    def test_un_socio_inscrito_no_queda_marcado_como_visita(self):
        self.registrar(socio=self.socio.id)

        self.socio.refresh_from_db()
        self.assertFalse(self.socio.es_visita)

    def test_si_ya_tiene_membresia_activa_no_se_le_cobra_la_visita(self):
        self.membresia(self.mensual)

        resp = self.registrar(socio=self.socio.id)

        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('socio', resp.data)

    def test_sin_socio_ni_nombre_se_rechaza(self):
        resp = self.registrar()

        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('nombre', resp.data)

    def test_no_acepta_un_socio_de_otro_gym(self):
        ajeno = Socio.objects.create(gym=self.otro_gym, nombre='Otro', apellido='Gym')

        resp = self.registrar(socio=ajeno.id)

        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('socio', resp.data)
