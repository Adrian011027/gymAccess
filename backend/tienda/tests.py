from decimal import Decimal

from rest_framework import status

from gyms.models import Sucursal
from gyms.tests import BaseAPITestCase
from notificaciones.models import Notificacion
from usuarios.models import Usuario
from .models import Producto, StockSucursal, Venta, VentaItem


def crear_producto(gym, sucursal, nombre, precio, stock=0, costo=0, stock_minimo=5):
    """Producto + sus existencias en una sucursal.

    El catálogo y el inventario viven en tablas distintas desde que el stock es por
    sucursal, así que las pruebas necesitan armar ambos.
    """
    producto = Producto.objects.create(gym=gym, nombre=nombre, precio=precio, costo=costo)
    if sucursal is not None:
        StockSucursal.objects.create(
            producto=producto, sucursal=sucursal, cantidad=stock, stock_minimo=stock_minimo,
        )
    return producto


class ProductoCRUDTests(BaseAPITestCase):
    def test_create_producto_asigna_gym_del_usuario(self):
        resp = self.client.post('/api/tienda/productos/', {
            'nombre': 'Agua 600ml', 'categoria': 'bebida',
            'precio': '20.00', 'costo': '8.00',
        })
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        self.assertEqual(Producto.objects.get(id=resp.data['id']).gym_id, self.gym.id)

    def test_create_producto_abre_stock_en_todas_las_sucursales(self):
        norte = Sucursal.objects.create(gym=self.gym, nombre='Norte')
        resp = self.client.post('/api/tienda/productos/', {
            'nombre': 'Agua', 'categoria': 'bebida', 'precio': '20',
        })
        producto = Producto.objects.get(id=resp.data['id'])
        self.assertEqual(producto.stocks.count(), 2)
        self.assertEqual(producto.stock_en(self.sucursal.id), 0)
        self.assertEqual(producto.stock_en(norte.id), 0)

    def test_stock_inicial_va_a_la_sucursal_pedida(self):
        norte = Sucursal.objects.create(gym=self.gym, nombre='Norte')
        resp = self.client.post(
            f'/api/tienda/productos/?sucursal={norte.id}',
            {'nombre': 'Agua', 'categoria': 'bebida', 'precio': '20', 'stock_inicial': 40},
        )
        producto = Producto.objects.get(id=resp.data['id'])
        self.assertEqual(producto.stock_en(norte.id), 40)
        self.assertEqual(producto.stock_en(self.sucursal.id), 0)

    def test_gym_enviado_por_el_cliente_es_ignorado(self):
        resp = self.client.post('/api/tienda/productos/', {
            'nombre': 'Powerade', 'categoria': 'bebida', 'precio': '30',
            'gym': self.otro_gym.id,
        })
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        self.assertEqual(Producto.objects.get(id=resp.data['id']).gym_id, self.gym.id)

    def test_list_solo_productos_del_gym(self):
        crear_producto(self.gym, self.sucursal, 'Agua', 20, stock=10)
        crear_producto(self.otro_gym, None, 'Ajeno', 20)
        resp = self.client.get('/api/tienda/productos/')
        nombres = [p['nombre'] for p in resp.data]
        self.assertIn('Agua', nombres)
        self.assertNotIn('Ajeno', nombres)

    def test_producto_de_otro_gym_da_404(self):
        ajeno = crear_producto(self.otro_gym, None, 'Ajeno', 20)
        resp = self.client.get(f'/api/tienda/productos/{ajeno.id}/')
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_delete_es_baja_logica(self):
        producto = crear_producto(self.gym, self.sucursal, 'Agua', 20, stock=10)
        resp = self.client.delete(f'/api/tienda/productos/{producto.id}/')
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)
        producto.refresh_from_db()
        self.assertFalse(producto.activo)

    def test_recepcion_lee_pero_no_edita_precios(self):
        producto = crear_producto(self.gym, self.sucursal, 'Agua', 20, stock=10)
        recepcion = Usuario.objects.create_user(
            email='caja@round3.com', password='Passw0rd1', nombre='Caja',
            rol='recepcion', gym=self.gym, sucursal=self.sucursal,
        )
        self.authenticate(recepcion)
        self.assertEqual(self.client.get('/api/tienda/productos/').status_code, status.HTTP_200_OK)
        resp = self.client.patch(f'/api/tienda/productos/{producto.id}/', {'precio': '1.00'})
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)


class AjusteStockTests(BaseAPITestCase):
    def setUp(self):
        super().setUp()
        self.norte = Sucursal.objects.create(gym=self.gym, nombre='Norte')
        self.agua = crear_producto(self.gym, self.sucursal, 'Agua', 20, stock=10)

    def url(self, producto=None):
        return f'/api/tienda/productos/{(producto or self.agua).id}/stock/'

    def test_fijar_cantidad_en_una_sucursal(self):
        resp = self.client.post(self.url(), {'sucursal': self.norte.id, 'cantidad': 25})
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.assertEqual(self.agua.stock_en(self.norte.id), 25)
        # y no toca la otra
        self.assertEqual(self.agua.stock_en(self.sucursal.id), 10)

    def test_ajustar_solo_el_minimo(self):
        resp = self.client.post(self.url(), {'sucursal': self.sucursal.id, 'stock_minimo': 3})
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        fila = StockSucursal.objects.get(producto=self.agua, sucursal=self.sucursal)
        self.assertEqual(fila.stock_minimo, 3)
        self.assertEqual(fila.cantidad, 10)

    def test_body_vacio_rechazado(self):
        resp = self.client.post(self.url(), {'sucursal': self.sucursal.id})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_sucursal_de_otro_gym_rechazada(self):
        ajena = Sucursal.objects.create(gym=self.otro_gym, nombre='Ajena')
        resp = self.client.post(self.url(), {'sucursal': ajena.id, 'cantidad': 5})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_recepcion_no_ajusta_stock(self):
        recepcion = Usuario.objects.create_user(
            email='caja@round3.com', password='Passw0rd1', nombre='Caja',
            rol='recepcion', gym=self.gym, sucursal=self.sucursal,
        )
        self.authenticate(recepcion)
        resp = self.client.post(self.url(), {'sucursal': self.sucursal.id, 'cantidad': 999})
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)


class VentaTests(BaseAPITestCase):
    def setUp(self):
        super().setUp()
        self.agua = crear_producto(
            self.gym, self.sucursal, 'Agua 600ml', Decimal('20.00'),
            stock=10, costo=Decimal('8.00'), stock_minimo=2,
        )
        self.barra = crear_producto(
            self.gym, self.sucursal, 'Barra proteica', Decimal('45.50'),
            stock=10, costo=Decimal('25.00'), stock_minimo=2,
        )

    def stock(self, producto):
        return producto.stock_en(self.sucursal.id)

    def _vender(self, items, metodo='efectivo', sucursal=None):
        return self.client.post('/api/tienda/ventas/', {
            'sucursal': sucursal or self.sucursal.id,
            'metodo': metodo,
            'items': items,
        }, format='json')

    def test_venta_calcula_total_en_el_servidor(self):
        resp = self._vender([
            {'producto': self.agua.id, 'cantidad': 2},
            {'producto': self.barra.id, 'cantidad': 1},
        ])
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        self.assertEqual(Decimal(resp.data['total']), Decimal('85.50'))

    def test_venta_descuenta_stock(self):
        self._vender([{'producto': self.agua.id, 'cantidad': 3}])
        self.assertEqual(self.stock(self.agua), 7)

    def test_stock_insuficiente_rechaza_y_no_deja_venta_a_medias(self):
        resp = self._vender([
            {'producto': self.agua.id, 'cantidad': 1},
            {'producto': self.barra.id, 'cantidad': 99},
        ])
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Venta.objects.count(), 0)
        self.assertEqual(self.stock(self.agua), 10)

    def test_precio_queda_congelado_en_el_item(self):
        self._vender([{'producto': self.agua.id, 'cantidad': 1}])
        self.agua.precio = Decimal('35.00')
        self.agua.save()
        item = VentaItem.objects.get(producto=self.agua)
        self.assertEqual(item.precio_unitario, Decimal('20.00'))
        self.assertEqual(item.subtotal, Decimal('20.00'))

    def test_no_se_puede_vender_producto_de_otro_gym(self):
        ajena = Sucursal.objects.create(gym=self.otro_gym, nombre='Ajena')
        ajeno = crear_producto(self.otro_gym, ajena, 'Ajeno', 10, stock=50)
        resp = self._vender([{'producto': ajeno.id, 'cantidad': 1}])
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Venta.objects.count(), 0)
        self.assertEqual(ajeno.stock_en(ajena.id), 50)

    def test_no_se_puede_vender_en_sucursal_de_otro_gym(self):
        ajena = Sucursal.objects.create(gym=self.otro_gym, nombre='Sucursal Ajena')
        resp = self._vender([{'producto': self.agua.id, 'cantidad': 1}], sucursal=ajena.id)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Venta.objects.count(), 0)

    def test_carrito_vacio_rechazado(self):
        self.assertEqual(self._vender([]).status_code, status.HTTP_400_BAD_REQUEST)

    def test_cantidad_cero_o_negativa_rechazada(self):
        self.assertEqual(
            self._vender([{'producto': self.agua.id, 'cantidad': 0}]).status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.assertEqual(
            self._vender([{'producto': self.agua.id, 'cantidad': -5}]).status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.assertEqual(self.stock(self.agua), 10)

    def test_producto_duplicado_en_el_carrito_rechazado(self):
        resp = self._vender([
            {'producto': self.agua.id, 'cantidad': 1},
            {'producto': self.agua.id, 'cantidad': 1},
        ])
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_venta_registra_al_cajero(self):
        resp = self._vender([{'producto': self.agua.id, 'cantidad': 1}])
        self.assertEqual(Venta.objects.get(id=resp.data['id']).vendido_por_id, self.user.id)

    def test_stock_bajo_genera_notificacion(self):
        self._vender([{'producto': self.agua.id, 'cantidad': 9}])  # deja 1, mínimo 2
        noti = Notificacion.objects.filter(tipo='inventario', gym=self.gym).first()
        self.assertIsNotNone(noti)
        self.assertIn('Agua 600ml', noti.mensaje)
        self.assertIn(self.sucursal.nombre, noti.mensaje)

    def test_venta_no_se_puede_editar_ni_borrar(self):
        resp = self._vender([{'producto': self.agua.id, 'cantidad': 1}])
        venta_id = resp.data['id']
        self.assertEqual(
            self.client.patch(f'/api/tienda/ventas/{venta_id}/', {'total': '1.00'}).status_code,
            status.HTTP_405_METHOD_NOT_ALLOWED,
        )
        self.assertEqual(
            self.client.delete(f'/api/tienda/ventas/{venta_id}/').status_code,
            status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    def test_list_ventas_aislado_por_gym(self):
        self._vender([{'producto': self.agua.id, 'cantidad': 1}])
        otra_sucursal = Sucursal.objects.create(gym=self.otro_gym, nombre='Ajena')
        Venta.objects.create(
            gym=self.otro_gym, sucursal=otra_sucursal, total=Decimal('999'), metodo='efectivo',
        )
        resp = self.client.get('/api/tienda/ventas/')
        self.assertEqual(len(resp.data), 1)
        self.assertEqual(Decimal(resp.data[0]['total']), Decimal('20.00'))

    def test_recepcion_puede_vender(self):
        recepcion = Usuario.objects.create_user(
            email='caja@round3.com', password='Passw0rd1', nombre='Caja',
            rol='recepcion', gym=self.gym, sucursal=self.sucursal,
        )
        self.authenticate(recepcion)
        resp = self._vender([{'producto': self.agua.id, 'cantidad': 1}])
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)

    def test_ventas_requieren_auth(self):
        self.client.credentials()
        self.assertEqual(
            self.client.get('/api/tienda/ventas/').status_code,
            status.HTTP_401_UNAUTHORIZED,
        )


class StockPorSucursalTests(BaseAPITestCase):
    """Lo que la Fase 2 vino a arreglar: dos cajas, dos inventarios."""

    def setUp(self):
        super().setUp()
        self.centro = self.sucursal
        self.norte = Sucursal.objects.create(gym=self.gym, nombre='Norte')
        self.agua = crear_producto(self.gym, self.centro, 'Agua', Decimal('20'), stock=10)
        StockSucursal.objects.create(producto=self.agua, sucursal=self.norte, cantidad=3)

    def vender_en(self, sucursal, cantidad):
        return self.client.post('/api/tienda/ventas/', {
            'sucursal': sucursal.id, 'metodo': 'efectivo',
            'items': [{'producto': self.agua.id, 'cantidad': cantidad}],
        }, format='json')

    def test_vender_en_una_no_toca_el_stock_de_la_otra(self):
        self.vender_en(self.centro, 4)
        self.assertEqual(self.agua.stock_en(self.centro.id), 6)
        self.assertEqual(self.agua.stock_en(self.norte.id), 3)

    def test_no_se_puede_vender_lo_que_hay_en_la_otra_sucursal(self):
        """Norte tiene 3; que Centro tenga 10 no le sirve."""
        resp = self.vender_en(self.norte, 5)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Norte', str(resp.data))
        self.assertEqual(self.agua.stock_en(self.norte.id), 3)

    def test_producto_expone_stock_de_la_sucursal_del_usuario(self):
        recepcion = Usuario.objects.create_user(
            email='norte@round3.com', password='Passw0rd1', nombre='Norte',
            rol='recepcion', gym=self.gym, sucursal=self.norte,
        )
        self.authenticate(recepcion)
        resp = self.client.get('/api/tienda/productos/')
        self.assertEqual(resp.data[0]['stock'], 3)

    def test_duenio_ve_el_total_y_el_desglose(self):
        resp = self.client.get('/api/tienda/productos/')
        producto = resp.data[0]
        self.assertEqual(producto['stock_total'], 13)
        self.assertEqual(producto['stock'], 13)   # sin sucursal de contexto, el total
        desglose = {s['sucursal_nombre']: s['cantidad'] for s in producto['stock_por_sucursal']}
        self.assertEqual(desglose, {'Centro': 10, 'Norte': 3})

    def test_duenio_puede_pedir_el_stock_de_una_sucursal(self):
        resp = self.client.get(f'/api/tienda/productos/?sucursal={self.norte.id}')
        self.assertEqual(resp.data[0]['stock'], 3)


class ResumenTests(BaseAPITestCase):
    def setUp(self):
        super().setUp()
        self.agua = crear_producto(
            self.gym, self.sucursal, 'Agua', Decimal('20.00'), stock=100, costo=Decimal('8.00'),
        )

    def test_resumen_calcula_margen(self):
        self.client.post('/api/tienda/ventas/', {
            'sucursal': self.sucursal.id, 'metodo': 'efectivo',
            'items': [{'producto': self.agua.id, 'cantidad': 5}],
        }, format='json')
        resp = self.client.get('/api/tienda/ventas/resumen/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(Decimal(resp.data['total_ventas']), Decimal('100.00'))
        self.assertEqual(Decimal(resp.data['costo_mercancia']), Decimal('40.00'))
        self.assertEqual(Decimal(resp.data['margen']), Decimal('60.00'))

    def test_resumen_sin_ventas_no_revienta(self):
        resp = self.client.get('/api/tienda/ventas/resumen/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(Decimal(resp.data['total_ventas']), Decimal('0'))
        self.assertEqual(resp.data['top_productos'], [])

    def test_resumen_no_incluye_ventas_de_otro_gym(self):
        otra = Sucursal.objects.create(gym=self.otro_gym, nombre='Ajena')
        Venta.objects.create(
            gym=self.otro_gym, sucursal=otra, total=Decimal('999'), metodo='efectivo',
        )
        resp = self.client.get('/api/tienda/ventas/resumen/')
        self.assertEqual(Decimal(resp.data['total_ventas']), Decimal('0'))

    def test_duenio_puede_filtrar_el_resumen_por_sucursal(self):
        norte = Sucursal.objects.create(gym=self.gym, nombre='Norte')
        Venta.objects.create(gym=self.gym, sucursal=self.sucursal, total=Decimal('100'), metodo='efectivo')
        Venta.objects.create(gym=self.gym, sucursal=norte, total=Decimal('40'), metodo='efectivo')

        todas = self.client.get('/api/tienda/ventas/resumen/')
        self.assertEqual(Decimal(todas.data['total_ventas']), Decimal('140'))
        solo_norte = self.client.get(f'/api/tienda/ventas/resumen/?sucursal={norte.id}')
        self.assertEqual(Decimal(solo_norte.data['total_ventas']), Decimal('40'))

    def test_sucursal_de_otro_gym_en_el_filtro_es_rechazada(self):
        ajena = Sucursal.objects.create(gym=self.otro_gym, nombre='Ajena')
        resp = self.client.get(f'/api/tienda/ventas/resumen/?sucursal={ajena.id}')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
