import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    """Solo crea la tabla. El traspaso de datos va en 0003 y el borrado de las
    columnas viejas en 0004: si se borrara aquí, el stock actual se perdería antes
    de haberlo copiado."""

    dependencies = [
        ('gyms', '0003_gym_politica_visitantes'),
        ('tienda', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='StockSucursal',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('cantidad', models.IntegerField(default=0)),
                ('stock_minimo', models.PositiveIntegerField(default=5)),
                ('producto', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='stocks', to='tienda.producto')),
                ('sucursal', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='stocks', to='gyms.sucursal')),
            ],
            options={
                'db_table': 'stock_sucursal',
                'ordering': ['sucursal__nombre'],
                'constraints': [models.UniqueConstraint(fields=('producto', 'sucursal'), name='stock_unico_por_producto_sucursal')],
            },
        ),
    ]
