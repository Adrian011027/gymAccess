"""El dueño mira un local concreto con ?sucursal=; a recepción se le ignora el parámetro."""

from datetime import date, timedelta
from decimal import Decimal

from rest_framework import status

from accesos.models import Acceso
from gyms.models import Clase, Equipamiento, Sucursal
from socios.models import Gasto, Membresia, Pago
from tienda.models import Venta
from usuarios.tests_sucursal import BaseDosSucursales


class FiltroSucursalTests(BaseDosSucursales):
    def setUp(self):
        super().setUp()
        self.socio_c, self.m_c = self.socio_en(self.centro, 'AnaCentro')
        self.socio_n, self.m_n = self.socio_en(self.norte, 'BetoNorte')

    def test_membresias_filtradas(self):
        self.assertEqual(len(self.client.get('/api/socios/membresias/').data), 2)
        resp = self.client.get(f'/api/socios/membresias/?sucursal={self.norte.id}')
        self.assertEqual(len(resp.data), 1)
        self.assertEqual(resp.data[0]['socio_nombre'], 'BetoNorte Test')

    def test_accesos_filtrados(self):
        Acceso.objects.create(socio=self.socio_c, sucursal=self.centro, resultado='permitido')
        Acceso.objects.create(socio=self.socio_n, sucursal=self.norte, resultado='permitido')
        self.assertEqual(len(self.client.get('/api/accesos/').data), 2)
        self.assertEqual(
            len(self.client.get(f'/api/accesos/?sucursal={self.centro.id}').data), 1,
        )

    def test_pagos_filtrados(self):
        Pago.objects.create(membresia=self.m_c, monto=Decimal('500'), metodo='efectivo')
        Pago.objects.create(membresia=self.m_n, monto=Decimal('300'), metodo='efectivo')
        resp = self.client.get(f'/api/socios/pagos/?sucursal={self.norte.id}')
        self.assertEqual(len(resp.data), 1)
        self.assertEqual(Decimal(resp.data[0]['monto']), Decimal('300'))

    def test_stats_filtradas(self):
        Acceso.objects.create(socio=self.socio_c, sucursal=self.centro, resultado='permitido')
        for _ in range(3):
            Acceso.objects.create(socio=self.socio_n, sucursal=self.norte, resultado='permitido')
        self.assertEqual(self.client.get('/api/accesos/stats/').data['accesos_hoy'], 4)
        resp = self.client.get(f'/api/accesos/stats/?sucursal={self.norte.id}')
        self.assertEqual(resp.data['accesos_hoy'], 3)

    def test_ventas_filtradas(self):
        Venta.objects.create(gym=self.gym, sucursal=self.centro, total=Decimal('100'), metodo='efectivo')
        Venta.objects.create(gym=self.gym, sucursal=self.norte, total=Decimal('40'), metodo='efectivo')
        resp = self.client.get(f'/api/tienda/ventas/?sucursal={self.centro.id}')
        self.assertEqual(len(resp.data), 1)

    def test_sucursal_de_otro_gym_rechazada(self):
        ajena = Sucursal.objects.create(gym=self.otro_gym, nombre='Ajena')
        resp = self.client.get(f'/api/socios/membresias/?sucursal={ajena.id}')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_sucursal_no_numerica_rechazada(self):
        resp = self.client.get('/api/socios/membresias/?sucursal=abc')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_recepcion_no_puede_espiar_la_otra_sucursal_con_el_parametro(self):
        """El filtro es una comodidad del dueño, no una puerta para salirse del alcance."""
        self.authenticate(self.recep_norte)
        resp = self.client.get(f'/api/socios/membresias/?sucursal={self.centro.id}')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data), 1)
        self.assertEqual(resp.data[0]['socio_nombre'], 'BetoNorte Test')


class ClaseEquipamientoGastoTests(BaseDosSucursales):
    def setUp(self):
        super().setUp()
        self.clase_norte = Clase.objects.create(
            gym=self.gym, sucursal=self.norte, nombre='Box Norte', tipo='fisico',
            profesor='X', hora_inicio='07:00', hora_fin='08:00', dias='Lun',
        )
        self.clase_todas = Clase.objects.create(
            gym=self.gym, sucursal=None, nombre='Clase General', tipo='fisico',
            profesor='Y', hora_inicio='09:00', hora_fin='10:00', dias='Mar',
        )
        Equipamiento.objects.create(gym=self.gym, sucursal=self.centro, nombre='Ring Centro', categoria='impacto')
        Equipamiento.objects.create(gym=self.gym, sucursal=self.norte, nombre='Costal Norte', categoria='impacto')
        Gasto.objects.create(gym=self.gym, sucursal=self.centro, categoria='renta',
                             descripcion='Renta Centro', monto=Decimal('18000'), fecha=date.today())
        Gasto.objects.create(gym=self.gym, sucursal=None, categoria='marketing',
                             descripcion='Campaña general', monto=Decimal('3000'), fecha=date.today())

    def test_clase_sin_sucursal_se_ve_desde_todas(self):
        self.authenticate(self.recep_norte)
        nombres = [c['nombre'] for c in self.client.get('/api/gyms/clases/').data]
        self.assertIn('Box Norte', nombres)
        self.assertIn('Clase General', nombres)

    def test_clase_de_otra_sucursal_no_se_ve(self):
        self.authenticate(self.recep_centro)
        nombres = [c['nombre'] for c in self.client.get('/api/gyms/clases/').data]
        self.assertNotIn('Box Norte', nombres)
        self.assertIn('Clase General', nombres)

    def test_duenio_ve_todas_las_clases(self):
        self.assertEqual(len(self.client.get('/api/gyms/clases/').data), 2)

    def test_equipamiento_acotado(self):
        nombres = [e['nombre'] for e in self.client.get('/api/gyms/equipamiento/').data]
        self.assertEqual(sorted(nombres), ['Costal Norte', 'Ring Centro'])
        resp = self.client.get(f'/api/gyms/equipamiento/?sucursal={self.norte.id}')
        self.assertEqual([e['nombre'] for e in resp.data], ['Costal Norte'])

    def test_gasto_sin_sucursal_cuenta_para_todas(self):
        resp = self.client.get(f'/api/socios/gastos/?sucursal={self.norte.id}')
        descripciones = [g['descripcion'] for g in resp.data]
        self.assertIn('Campaña general', descripciones)
        self.assertNotIn('Renta Centro', descripciones)

    def test_gasto_de_su_sucursal_mas_los_generales(self):
        resp = self.client.get(f'/api/socios/gastos/?sucursal={self.centro.id}')
        descripciones = sorted(g['descripcion'] for g in resp.data)
        self.assertEqual(descripciones, ['Campaña general', 'Renta Centro'])

    def test_clase_nueva_hereda_la_sucursal_de_quien_la_crea(self):
        self.authenticate(self.recep_norte)
        resp = self.client.post('/api/gyms/clases/', {
            'nombre': 'Nueva', 'tipo': 'fisico', 'profesor': 'Z',
            'hora_inicio': '11:00', 'hora_fin': '12:00', 'dias': 'Vie',
        })
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        self.assertEqual(Clase.objects.get(id=resp.data['id']).sucursal_id, self.norte.id)

    def test_no_puede_crear_clase_en_otra_sucursal(self):
        self.authenticate(self.recep_norte)
        resp = self.client.post('/api/gyms/clases/', {
            'nombre': 'Intrusa', 'tipo': 'fisico', 'profesor': 'Z',
            'hora_inicio': '11:00', 'hora_fin': '12:00', 'dias': 'Vie',
            'sucursal': self.centro.id,
        })
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(Clase.objects.filter(nombre='Intrusa').exists())
