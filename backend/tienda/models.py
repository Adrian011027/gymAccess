from django.db import models

from gyms.models import Gym, Sucursal


class Producto(models.Model):
    CATEGORIA_CHOICES = [
        ('bebida', 'Bebidas'),
        ('suplemento', 'Suplementos'),
        ('snack', 'Snacks'),
        ('accesorio', 'Accesorios'),
        ('otro', 'Otro'),
    ]

    gym = models.ForeignKey(Gym, on_delete=models.CASCADE, related_name='productos')
    nombre = models.CharField(max_length=150)
    categoria = models.CharField(max_length=20, choices=CATEGORIA_CHOICES, default='bebida')
    precio = models.DecimalField(max_digits=10, decimal_places=2)
    # Costo de compra: sin él el reporte de tienda solo puede dar venta bruta, no margen.
    costo = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    activo = models.BooleanField(default=True)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'productos'
        ordering = ['categoria', 'nombre']

    def __str__(self):
        return f'{self.nombre} - ${self.precio}'

    def stock_en(self, sucursal_id):
        fila = self.stocks.filter(sucursal_id=sucursal_id).first()
        return fila.cantidad if fila else 0

    def stock_total(self):
        from django.db.models import Sum
        return self.stocks.aggregate(t=Sum('cantidad'))['t'] or 0


class StockSucursal(models.Model):
    """Existencias de un producto en una sucursal concreta.

    El catálogo (nombre, precio, costo) es del negocio; las piezas están en un local.
    Un solo contador para todas las sucursales hace que la caja de Norte descuente el
    agua de Centro, y el inventario deja de servir para reponer.
    """

    producto = models.ForeignKey(Producto, on_delete=models.CASCADE, related_name='stocks')
    sucursal = models.ForeignKey(Sucursal, on_delete=models.CASCADE, related_name='stocks')
    cantidad = models.IntegerField(default=0)
    stock_minimo = models.PositiveIntegerField(default=5)

    class Meta:
        db_table = 'stock_sucursal'
        constraints = [
            models.UniqueConstraint(
                fields=['producto', 'sucursal'], name='stock_unico_por_producto_sucursal',
            ),
        ]
        ordering = ['sucursal__nombre']

    def __str__(self):
        return f'{self.producto.nombre} @ {self.sucursal.nombre}: {self.cantidad}'

    @property
    def bajo(self):
        return self.cantidad <= self.stock_minimo


class Venta(models.Model):
    METODO_CHOICES = [
        ('efectivo', 'Efectivo'),
        ('tarjeta', 'Tarjeta'),
        ('transferencia', 'Transferencia'),
    ]

    gym = models.ForeignKey(Gym, on_delete=models.CASCADE, related_name='ventas')
    sucursal = models.ForeignKey(Sucursal, on_delete=models.PROTECT, related_name='ventas')
    total = models.DecimalField(max_digits=10, decimal_places=2)
    metodo = models.CharField(max_length=20, choices=METODO_CHOICES)
    vendido_por = models.ForeignKey(
        'usuarios.Usuario', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='ventas_registradas'
    )
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'ventas'
        ordering = ['-fecha']
        indexes = [
            models.Index(fields=['gym', 'fecha']),
        ]

    def __str__(self):
        return f'Venta #{self.id} - ${self.total}'


class VentaItem(models.Model):
    venta = models.ForeignKey(Venta, on_delete=models.CASCADE, related_name='items')
    # PROTECT: un producto con ventas no se borra, o el histórico pierde el renglón.
    producto = models.ForeignKey(Producto, on_delete=models.PROTECT, related_name='ventas')
    cantidad = models.PositiveIntegerField()
    # Copia del precio al momento de cobrar. Si el reporte leyera Producto.precio,
    # subir el agua de $20 a $25 reescribiría los meses ya vendidos.
    precio_unitario = models.DecimalField(max_digits=10, decimal_places=2)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        db_table = 'venta_items'

    def __str__(self):
        return f'{self.cantidad} x {self.producto.nombre}'
