"""Corte de caja del día: /api/socios/pagos/corte/

La pregunta que contesta el endpoint es la que recepción no podía contestar al cerrar:
cuánto entró hoy en esta caja, por qué vía entró, y cuánto efectivo debería haber en
el cajón. El dinero llega por tres puertas (membresías, tienda y gastos que salen de
la caja) y hasta ahora cada una vivía en su propia pantalla.
"""

from datetime import date, timedelta
from decimal import Decimal

from django.utils import timezone
from rest_framework import status

from gyms.models import Sucursal
from gyms.tests import BaseAPITestCase
from tienda.models import Producto, StockSucursal, Venta, VentaItem
from usuarios.models import Usuario
from .models import Gasto, Membresia, Pago, Plan, Socio

URL = '/api/socios/pagos/corte/'


class CorteBase(BaseAPITestCase):
    def setUp(self):
        super().setUp()
        self.plan = Plan.objects.create(
            gym=self.gym, nombre='Mensual', tipo='mensual', precio=500, duracion_dias=30,
        )
        self.hoy = timezone.localdate()

    def cobrar_membresia(self, monto, metodo='efectivo', sucursal=None, dias_atras=0,
                         nombre='Socio'):
        socio = Socio.objects.create(gym=self.gym, nombre=nombre, apellido='Test')
        membresia = Membresia.objects.create(
            socio=socio, plan=self.plan, sucursal=sucursal or self.sucursal,
            fecha_inicio=self.hoy, fecha_fin=self.hoy + timedelta(days=30), estado='activa',
        )
        pago = Pago.objects.create(membresia=membresia, monto=monto, metodo=metodo)
        self._mover_fecha(Pago, pago.id, dias_atras)
        return pago

    def vender(self, monto, metodo='efectivo', sucursal=None, dias_atras=0,
               nombre='Agua', cantidad=1):
        producto = Producto.objects.create(gym=self.gym, nombre=nombre, precio=monto)
        StockSucursal.objects.create(
            producto=producto, sucursal=sucursal or self.sucursal, cantidad=100,
        )
        venta = Venta.objects.create(
            gym=self.gym, sucursal=sucursal or self.sucursal,
            total=Decimal(monto) * cantidad, metodo=metodo, vendido_por=self.user,
        )
        VentaItem.objects.create(
            venta=venta, producto=producto, cantidad=cantidad,
            precio_unitario=monto, subtotal=Decimal(monto) * cantidad,
        )
        self._mover_fecha(Venta, venta.id, dias_atras)
        return venta

    def gastar(self, monto, metodo='efectivo', sucursal=..., dias_atras=0,
               categoria='otro', descripcion='Garrafón'):
        return Gasto.objects.create(
            gym=self.gym,
            sucursal=self.sucursal if sucursal is ... else sucursal,
            categoria=categoria, descripcion=descripcion, monto=monto, metodo=metodo,
            fecha=self.hoy - timedelta(days=dias_atras),
        )

    def _mover_fecha(self, modelo, pk, dias_atras):
        """`fecha` es auto_now_add, así que para fechar en el pasado hay que hacer UPDATE."""
        if dias_atras:
            modelo.objects.filter(pk=pk).update(
                fecha=timezone.now() - timedelta(days=dias_atras),
            )

    def corte(self, **params):
        query = '&'.join(f'{k}={v}' for k, v in params.items())
        resp = self.client.get(f'{URL}?{query}' if query else URL)
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        return resp.data


class CorteSumaLasTresFuentesTests(CorteBase):
    """El total del día es cobros de membresía + tienda − gastos, en una sola pantalla."""

    def test_suma_membresias_y_ventas_del_dia(self):
        self.cobrar_membresia(500)
        self.cobrar_membresia(300, nombre='Otro')
        self.vender(20, cantidad=2)

        datos = self.corte()

        self.assertEqual(Decimal(str(datos['membresias']['total'])), Decimal('800'))
        self.assertEqual(datos['membresias']['num'], 2)
        self.assertEqual(Decimal(str(datos['tienda']['total'])), Decimal('40'))
        self.assertEqual(datos['tienda']['num'], 1)
        self.assertEqual(Decimal(str(datos['ingresos']['total'])), Decimal('840'))

    def test_gastos_restan_del_neto(self):
        self.cobrar_membresia(500)
        self.gastar(120)

        datos = self.corte()

        self.assertEqual(Decimal(str(datos['gastos']['total'])), Decimal('120'))
        self.assertEqual(Decimal(str(datos['neto'])), Decimal('380'))

    def test_dia_sin_movimientos_devuelve_ceros_y_no_revienta(self):
        datos = self.corte()

        self.assertEqual(Decimal(str(datos['ingresos']['total'])), Decimal('0'))
        self.assertEqual(Decimal(str(datos['neto'])), Decimal('0'))
        self.assertEqual(Decimal(str(datos['efectivo_esperado'])), Decimal('0'))
        self.assertEqual(datos['movimientos'], [])


class CorteDesglosePorMetodoTests(CorteBase):
    """El cajón solo recibe efectivo: mezclar tarjeta en la cuenta manda a recepción a
    buscar un faltante que nunca existió."""

    def test_efectivo_esperado_ignora_tarjeta_y_transferencia(self):
        self.cobrar_membresia(500, metodo='efectivo')
        self.cobrar_membresia(700, metodo='tarjeta', nombre='Tarjeta')
        self.vender(50, metodo='transferencia')
        self.vender(30, metodo='efectivo', nombre='Powerade')

        datos = self.corte()

        por_metodo = datos['ingresos']['por_metodo']
        self.assertEqual(Decimal(str(por_metodo['efectivo'])), Decimal('530'))
        self.assertEqual(Decimal(str(por_metodo['tarjeta'])), Decimal('700'))
        self.assertEqual(Decimal(str(por_metodo['transferencia'])), Decimal('50'))
        self.assertEqual(Decimal(str(datos['efectivo_esperado'])), Decimal('530'))

    def test_gasto_por_transferencia_no_baja_el_efectivo_del_cajon(self):
        self.cobrar_membresia(500, metodo='efectivo')
        self.gastar(200, metodo='transferencia', categoria='renta', descripcion='Renta')

        datos = self.corte()

        # El neto del negocio sí baja; el efectivo del cajón no, porque la renta
        # salió del banco.
        self.assertEqual(Decimal(str(datos['neto'])), Decimal('300'))
        self.assertEqual(Decimal(str(datos['efectivo_esperado'])), Decimal('500'))

    def test_gasto_en_efectivo_si_baja_el_cajon(self):
        self.cobrar_membresia(500, metodo='efectivo')
        self.gastar(200, metodo='efectivo')

        datos = self.corte()

        self.assertEqual(Decimal(str(datos['efectivo_esperado'])), Decimal('300'))


class CorteFechaTests(CorteBase):
    """Un corte es de un día. Si arrastra lo de ayer, no sirve para cuadrar nada."""

    def test_movimientos_de_ayer_no_entran_al_corte_de_hoy(self):
        self.cobrar_membresia(500, dias_atras=1)
        self.vender(20, dias_atras=1)
        self.gastar(100, dias_atras=1)

        datos = self.corte()

        self.assertEqual(Decimal(str(datos['ingresos']['total'])), Decimal('0'))
        self.assertEqual(Decimal(str(datos['gastos']['total'])), Decimal('0'))

    def test_fecha_explicita_trae_el_corte_de_ese_dia(self):
        self.cobrar_membresia(500, dias_atras=1)
        self.cobrar_membresia(80, nombre='Hoy')

        ayer = (self.hoy - timedelta(days=1)).isoformat()
        datos = self.corte(fecha=ayer)

        self.assertEqual(datos['fecha'], ayer)
        self.assertEqual(Decimal(str(datos['ingresos']['total'])), Decimal('500'))

    def test_fecha_invalida_es_400_y_no_un_corte_vacio(self):
        resp = self.client.get(f'{URL}?fecha=31-12-2026')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('fecha', resp.data)

    def test_sin_fecha_el_corte_es_el_de_hoy(self):
        datos = self.corte()
        self.assertEqual(datos['fecha'], self.hoy.isoformat())


class CorteAisladoPorSucursalTests(CorteBase):
    """Recepción cuadra su cajón, no el del local de al lado."""

    def setUp(self):
        super().setUp()
        self.norte = Sucursal.objects.create(gym=self.gym, nombre='Norte')
        self.recepcion = Usuario.objects.create_user(
            email='recepcion@round3.com', password='Passw0rd1', nombre='Marisol',
            rol='recepcion', gym=self.gym, sucursal=self.sucursal,
        )

    def test_recepcion_solo_ve_los_movimientos_de_su_sucursal(self):
        self.cobrar_membresia(500, sucursal=self.sucursal)
        self.cobrar_membresia(900, sucursal=self.norte, nombre='Norte')
        self.vender(20, sucursal=self.sucursal)
        self.vender(70, sucursal=self.norte, nombre='Proteína')

        self.authenticate(self.recepcion)
        datos = self.corte()

        self.assertEqual(Decimal(str(datos['ingresos']['total'])), Decimal('520'))
        self.assertEqual(datos['sucursal']['nombre'], 'Centro')

    def test_recepcion_no_puede_espiar_el_corte_de_otra_sucursal_por_query(self):
        self.cobrar_membresia(900, sucursal=self.norte, nombre='Norte')
        self.cobrar_membresia(100, sucursal=self.sucursal)

        self.authenticate(self.recepcion)
        datos = self.corte(sucursal=self.norte.id)

        self.assertEqual(Decimal(str(datos['ingresos']['total'])), Decimal('100'))

    def test_el_dueno_ve_todo_el_gym_y_puede_pedir_una_sucursal(self):
        self.cobrar_membresia(500, sucursal=self.sucursal)
        self.cobrar_membresia(900, sucursal=self.norte, nombre='Norte')

        completo = self.corte()
        self.assertEqual(Decimal(str(completo['ingresos']['total'])), Decimal('1400'))
        self.assertIsNone(completo['sucursal'])

        solo_norte = self.corte(sucursal=self.norte.id)
        self.assertEqual(Decimal(str(solo_norte['ingresos']['total'])), Decimal('900'))
        self.assertEqual(solo_norte['sucursal']['nombre'], 'Norte')

    def test_gasto_del_negocio_no_entra_al_corte_de_una_sucursal(self):
        """Un gasto sin sucursal (renta del corporativo, contador) no salió de este
        cajón: contarlo en cada caja lo restaría una vez por local."""
        self.cobrar_membresia(500, sucursal=self.sucursal)
        self.gastar(300, sucursal=None, categoria='renta', descripcion='Contador')

        self.authenticate(self.recepcion)
        datos = self.corte()

        self.assertEqual(Decimal(str(datos['gastos']['total'])), Decimal('0'))
        self.assertEqual(Decimal(str(datos['neto'])), Decimal('500'))

    def test_el_dueno_si_ve_el_gasto_del_negocio_en_el_corte_completo(self):
        self.cobrar_membresia(500)
        self.gastar(300, sucursal=None, categoria='renta', descripcion='Contador')

        datos = self.corte()

        self.assertEqual(Decimal(str(datos['gastos']['total'])), Decimal('300'))

    def test_no_se_cuela_el_corte_de_otro_gym(self):
        otra_sucursal = Sucursal.objects.create(gym=self.otro_gym, nombre='Ajena')
        otro_plan = Plan.objects.create(
            gym=self.otro_gym, nombre='Mensual', tipo='mensual', precio=999, duracion_dias=30,
        )
        socio = Socio.objects.create(gym=self.otro_gym, nombre='Ajeno', apellido='X')
        membresia = Membresia.objects.create(
            socio=socio, plan=otro_plan, sucursal=otra_sucursal,
            fecha_inicio=self.hoy, fecha_fin=self.hoy + timedelta(days=30), estado='activa',
        )
        Pago.objects.create(membresia=membresia, monto=999, metodo='efectivo')
        Venta.objects.create(
            gym=self.otro_gym, sucursal=otra_sucursal, total=Decimal('50'), metodo='efectivo',
        )

        datos = self.corte()

        self.assertEqual(Decimal(str(datos['ingresos']['total'])), Decimal('0'))


class CorteMovimientosTests(CorteBase):
    """La lista de movimientos es el respaldo del número: sin ella el corte es un
    total que nadie puede auditar cuando no cuadra."""

    def test_cada_movimiento_trae_concepto_metodo_y_quien_lo_registro(self):
        self.cobrar_membresia(500, nombre='Ana')
        self.vender(25, nombre='Powerade', cantidad=2)
        self.gastar(60, descripcion='Garrafón')

        movimientos = self.corte()['movimientos']

        self.assertEqual(len(movimientos), 3)
        por_tipo = {m['tipo']: m for m in movimientos}
        self.assertIn('Ana', por_tipo['membresia']['concepto'])
        self.assertIn('Mensual', por_tipo['membresia']['concepto'])
        self.assertEqual(por_tipo['tienda']['concepto'], '2× Powerade')
        self.assertEqual(por_tipo['tienda']['registrado_por'], 'Admin')
        self.assertIn('Garrafón', por_tipo['gasto']['concepto'])
        self.assertEqual(por_tipo['gasto']['signo'], -1)
        self.assertEqual(por_tipo['tienda']['signo'], 1)

    def test_los_gastos_van_al_final_porque_no_guardan_hora(self):
        self.gastar(60)
        self.cobrar_membresia(500)

        movimientos = self.corte()['movimientos']

        self.assertEqual([m['tipo'] for m in movimientos], ['membresia', 'gasto'])


class CorteRequiereAuthTests(CorteBase):
    def test_sin_token_no_hay_corte(self):
        self.client.credentials()
        resp = self.client.get(URL)
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)


class GastoParaElCorteTests(CorteBase):
    """El alta de gastos tiene que dejarlos donde el corte pueda encontrarlos.

    Un gasto sin método se descontaba del efectivo aunque se hubiera pagado por
    transferencia, y uno sin sucursal no aparece en el corte de ninguna caja: las dos
    cosas se deciden al guardarlo, no al leerlo.
    """

    def test_metodo_por_defecto_es_efectivo(self):
        resp = self.client.post('/api/socios/gastos/', {
            'categoria': 'otro', 'descripcion': 'Garrafones',
            'monto': '80.00', 'fecha': self.hoy.isoformat(),
        })
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        self.assertEqual(Gasto.objects.get(id=resp.data['id']).metodo, 'efectivo')

    def test_metodo_enviado_se_guarda_y_se_devuelve(self):
        resp = self.client.post('/api/socios/gastos/', {
            'categoria': 'renta', 'descripcion': 'Renta', 'metodo': 'transferencia',
            'monto': '8000.00', 'fecha': self.hoy.isoformat(),
        })
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        self.assertEqual(resp.data['metodo'], 'transferencia')
        self.assertEqual(Gasto.objects.get(id=resp.data['id']).metodo, 'transferencia')

    def test_metodo_invalido_se_rechaza(self):
        resp = self.client.post('/api/socios/gastos/', {
            'categoria': 'otro', 'descripcion': 'X', 'metodo': 'vales',
            'monto': '10.00', 'fecha': self.hoy.isoformat(),
        })
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_gasto_sin_sucursal_sigue_siendo_del_negocio(self):
        """El dueño no está atado a una caja: si no dice de cuál salió, es del negocio."""
        resp = self.client.post('/api/socios/gastos/', {
            'categoria': 'marketing', 'descripcion': 'Campaña',
            'monto': '3000.00', 'fecha': self.hoy.isoformat(),
        })
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        self.assertIsNone(Gasto.objects.get(id=resp.data['id']).sucursal_id)

    def test_gasto_hereda_la_sucursal_de_quien_lo_registra(self):
        """Un admin atado a una sucursal lo carga a su caja sin tener que decirlo."""
        admin_centro = Usuario.objects.create_user(
            email='admin.centro@round3.com', password='Passw0rd1', nombre='Admin Centro',
            rol='admin', gym=self.gym, sucursal=self.sucursal,
        )
        self.authenticate(admin_centro)
        resp = self.client.post('/api/socios/gastos/', {
            'categoria': 'servicios', 'descripcion': 'Luz',
            'monto': '900.00', 'fecha': self.hoy.isoformat(),
        })
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        self.assertEqual(Gasto.objects.get(id=resp.data['id']).sucursal_id, self.sucursal.id)

    def test_gasto_recien_creado_aparece_en_el_corte_de_esa_caja(self):
        """El recorrido completo: se registra desde Pagos y baja el efectivo del corte."""
        self.cobrar_membresia(500, metodo='efectivo')
        resp = self.client.post('/api/socios/gastos/', {
            'categoria': 'otro', 'descripcion': 'Garrafones', 'metodo': 'efectivo',
            'sucursal': self.sucursal.id,
            'monto': '80.00', 'fecha': self.hoy.isoformat(),
        })
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)

        datos = self.corte(sucursal=self.sucursal.id)
        self.assertEqual(Decimal(str(datos['gastos']['total'])), Decimal('80'))
        self.assertEqual(Decimal(str(datos['efectivo_esperado'])), Decimal('420'))
