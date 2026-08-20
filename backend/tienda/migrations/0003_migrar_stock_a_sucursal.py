from django.db import migrations


def repartir_stock(apps, schema_editor):
    """Baja el stock global de cada producto a las sucursales.

    Las piezas existen físicamente en algún lado, así que se cargan completas a la
    sucursal más antigua del gym (con una sola sucursal, la única posible). Repartirlas
    entre varias sería inventar un conteo que nadie hizo. Las demás sucursales arrancan
    en 0 y el dueño ajusta con el inventario en la mano.
    """
    Producto = apps.get_model('tienda', 'Producto')
    Sucursal = apps.get_model('gyms', 'Sucursal')
    StockSucursal = apps.get_model('tienda', 'StockSucursal')

    for producto in Producto.objects.all():
        sucursales = list(Sucursal.objects.filter(gym_id=producto.gym_id).order_by('id'))
        if not sucursales:
            continue
        for i, sucursal in enumerate(sucursales):
            StockSucursal.objects.get_or_create(
                producto_id=producto.id,
                sucursal_id=sucursal.id,
                defaults={
                    'cantidad': producto.stock if i == 0 else 0,
                    'stock_minimo': producto.stock_minimo,
                },
            )


def devolver_stock(apps, schema_editor):
    """Suma las existencias de vuelta a la columna global."""
    Producto = apps.get_model('tienda', 'Producto')
    StockSucursal = apps.get_model('tienda', 'StockSucursal')

    for producto in Producto.objects.all():
        filas = StockSucursal.objects.filter(producto_id=producto.id)
        producto.stock = sum(f.cantidad for f in filas)
        primera = filas.first()
        if primera:
            producto.stock_minimo = primera.stock_minimo
        producto.save(update_fields=['stock', 'stock_minimo'])


class Migration(migrations.Migration):

    dependencies = [
        ('tienda', '0002_stock_por_sucursal'),
    ]

    operations = [
        migrations.RunPython(repartir_stock, devolver_stock),
    ]
