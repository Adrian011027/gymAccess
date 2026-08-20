from django.db import migrations, models


class Migration(migrations.Migration):
    """Quita las columnas viejas, ya con los datos a salvo en stock_sucursal.

    Se borran en vez de dejarlas: dos contadores del mismo inventario se desincronizan
    y luego nadie sabe cuál es el bueno.
    """

    dependencies = [
        ('tienda', '0003_migrar_stock_a_sucursal'),
    ]

    operations = [
        migrations.RemoveField(model_name='producto', name='stock'),
        migrations.RemoveField(model_name='producto', name='stock_minimo'),
    ]
