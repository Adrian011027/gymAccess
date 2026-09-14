from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('socios', '0013_socio_es_visita'),
    ]

    operations = [
        migrations.AlterField(
            model_name='plan',
            name='tipo',
            field=models.CharField(choices=[
                ('semanal', 'Semanal'),
                ('mensual', 'Mensual'),
                ('trimestral', 'Trimestral'),
                ('semestral', 'Semestral'),
                ('anual', 'Anual'),
                ('visita', 'Visita Suelta'),
                ('clases', 'Paquete de Clases'),
            ], max_length=20),
        ),
    ]
