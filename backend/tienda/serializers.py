from decimal import Decimal

from django.db import transaction
from django.db.models import F
from rest_framework import serializers

from gyms.models import Sucursal
from notificaciones.models import Notificacion
from .models import Producto, StockSucursal, Venta, VentaItem


class StockSucursalSerializer(serializers.ModelSerializer):
    sucursal_nombre = serializers.CharField(source='sucursal.nombre', read_only=True)
    bajo = serializers.BooleanField(read_only=True)

    class Meta:
        model = StockSucursal
        fields = ['id', 'sucursal', 'sucursal_nombre', 'cantidad', 'stock_minimo', 'bajo']


class ProductoSerializer(serializers.ModelSerializer):
    # `stock` y `stock_bajo` son los de la sucursal en la que se está parado, para que
    # la caja no tenga que sumar nada. El desglose completo va aparte.
    stock = serializers.SerializerMethodField()
    stock_minimo = serializers.SerializerMethodField()
    stock_bajo = serializers.SerializerMethodField()
    stock_total = serializers.IntegerField(read_only=True)
    stock_por_sucursal = StockSucursalSerializer(source='stocks', many=True, read_only=True)
    # Solo al crear: existencias iniciales en la sucursal de contexto.
    stock_inicial = serializers.IntegerField(write_only=True, required=False, min_value=0)

    class Meta:
        model = Producto
        fields = [
            'id', 'gym', 'nombre', 'categoria', 'precio', 'costo', 'activo', 'creado_en',
            'stock', 'stock_minimo', 'stock_bajo', 'stock_total', 'stock_por_sucursal',
            'stock_inicial',
        ]
        read_only_fields = ['gym', 'creado_en']

    def _fila(self, obj):
        suc = self.context.get('sucursal_id')
        if suc is None:
            return None
        return next((s for s in obj.stocks.all() if s.sucursal_id == suc), None)

    def get_stock(self, obj):
        fila = self._fila(obj)
        # Sin sucursal de contexto (el dueño viendo todo) el número honesto es el total.
        return fila.cantidad if fila else obj.stock_total()

    def get_stock_minimo(self, obj):
        fila = self._fila(obj)
        if fila:
            return fila.stock_minimo
        filas = list(obj.stocks.all())
        return min((s.stock_minimo for s in filas), default=5)

    def get_stock_bajo(self, obj):
        fila = self._fila(obj)
        if fila:
            return fila.bajo
        # Para el dueño basta con que una sucursal esté baja para que valga la pena avisar.
        return any(s.bajo for s in obj.stocks.all())


class AjusteStockSerializer(serializers.Serializer):
    """Fija existencias. Ambos campos opcionales: se puede tocar solo el mínimo."""

    sucursal = serializers.IntegerField(required=False)
    cantidad = serializers.IntegerField(required=False, min_value=0)
    stock_minimo = serializers.IntegerField(required=False, min_value=0)

    def validate(self, attrs):
        if attrs.get('cantidad') is None and attrs.get('stock_minimo') is None:
            raise serializers.ValidationError('Indica cantidad o stock_minimo.')
        return attrs


class VentaItemSerializer(serializers.ModelSerializer):
    producto_nombre = serializers.CharField(source='producto.nombre', read_only=True)

    class Meta:
        model = VentaItem
        fields = ['id', 'producto', 'producto_nombre', 'cantidad', 'precio_unitario', 'subtotal']
        read_only_fields = ['precio_unitario', 'subtotal']


class VentaItemInputSerializer(serializers.Serializer):
    """Lo único que acepta el carrito: qué y cuánto. El precio lo pone el servidor."""

    producto = serializers.IntegerField()
    cantidad = serializers.IntegerField(min_value=1)


class VentaSerializer(serializers.ModelSerializer):
    items = VentaItemSerializer(many=True, read_only=True)
    vendido_por_nombre = serializers.CharField(source='vendido_por.nombre', read_only=True)
    sucursal_nombre = serializers.CharField(source='sucursal.nombre', read_only=True)

    class Meta:
        model = Venta
        fields = [
            'id', 'sucursal', 'sucursal_nombre', 'total', 'metodo',
            'vendido_por', 'vendido_por_nombre', 'fecha', 'items',
        ]
        read_only_fields = ['total', 'vendido_por', 'fecha', 'gym']


class VentaCreateSerializer(serializers.Serializer):
    sucursal = serializers.IntegerField()
    metodo = serializers.ChoiceField(choices=Venta.METODO_CHOICES)
    items = VentaItemInputSerializer(many=True, allow_empty=False)

    def validate_items(self, items):
        vistos = set()
        for it in items:
            if it['producto'] in vistos:
                raise serializers.ValidationError(
                    'El mismo producto aparece dos veces: súmalo en una sola línea.'
                )
            vistos.add(it['producto'])
        return items

    def create(self, validated):
        request = self.context['request']
        gym_id = request.user.gym_id

        try:
            sucursal = Sucursal.objects.get(id=validated['sucursal'], gym_id=gym_id)
        except Sucursal.DoesNotExist:
            raise serializers.ValidationError({'sucursal': 'Sucursal no encontrada'})

        # Recepción cobra en su caja. Sin esto, un POST con la sucursal de al lado
        # mete la venta en el corte del otro local.
        propia = getattr(request.user, 'sucursal_id', None)
        if propia is not None and sucursal.id != propia:
            raise serializers.ValidationError(
                {'sucursal': 'Solo puedes registrar ventas en tu sucursal.'}
            )

        pedidos = {it['producto']: it['cantidad'] for it in validated['items']}
        productos = {
            p.id: p for p in Producto.objects.filter(
                id__in=pedidos, gym_id=gym_id, activo=True,
            )
        }
        faltantes = [pid for pid in pedidos if pid not in productos]
        if faltantes:
            raise serializers.ValidationError(
                {'items': f'Producto no encontrado: {faltantes}'}
            )

        with transaction.atomic():
            venta = Venta(
                gym_id=gym_id,
                sucursal=sucursal,
                metodo=validated['metodo'],
                vendido_por=request.user,
                total=Decimal('0'),
            )

            total = Decimal('0')
            items = []
            for pid, cantidad in pedidos.items():
                producto = productos[pid]
                # UPDATE ... WHERE cantidad >= n: una sola sentencia atómica, así que
                # dos cajas cobrando el último Powerade a la vez no lo venden dos veces.
                # (No usamos select_for_update: SQLite no lo soporta y los tests corren ahí.)
                # Se descuenta del stock de ESTA sucursal, no de un contador compartido.
                afectadas = StockSucursal.objects.filter(
                    producto_id=pid, sucursal=sucursal, cantidad__gte=cantidad,
                ).update(cantidad=F('cantidad') - cantidad)
                if not afectadas:
                    disponible = producto.stock_en(sucursal.id)
                    raise serializers.ValidationError({
                        'items': f'Stock insuficiente de "{producto.nombre}" en '
                                 f'{sucursal.nombre} (quedan {disponible}, pediste {cantidad})'
                    })

                subtotal = producto.precio * cantidad
                total += subtotal
                items.append(VentaItem(
                    venta=venta,
                    producto=producto,
                    cantidad=cantidad,
                    precio_unitario=producto.precio,
                    subtotal=subtotal,
                ))

            venta.total = total
            venta.save()
            for item in items:
                item.venta = venta
            VentaItem.objects.bulk_create(items)

        self._avisar_stock_bajo(gym_id, pedidos.keys(), sucursal)
        return venta

    def _avisar_stock_bajo(self, gym_id, producto_ids, sucursal):
        """Fuera de la transacción: una notificación fallida no debe tumbar el cobro."""
        bajos = StockSucursal.objects.filter(
            producto_id__in=producto_ids, sucursal=sucursal, cantidad__lte=F('stock_minimo'),
        ).select_related('producto')
        for fila in bajos:
            Notificacion.objects.create(
                gym_id=gym_id,
                tipo='inventario',
                mensaje=f'Stock bajo en {sucursal.nombre}: quedan {fila.cantidad} '
                        f'de "{fila.producto.nombre}"',
                link='/pos?tab=inventario',
            )

    def to_representation(self, instance):
        return VentaSerializer(instance, context=self.context).data
