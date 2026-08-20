"""Asigna número de socio a los registros que existían antes de este campo.

Empieza en 1000 por gym, en el orden en que se dieron de alta (`creado_en`), que es
el mismo criterio que usa SocioViewSet.perform_create para los nuevos: continúa la
numeración donde la deja este backfill en vez de reiniciarla.
"""

from django.db import migrations


def asignar_numeros(apps, schema_editor):
    Socio = apps.get_model('socios', 'Socio')
    Gym = apps.get_model('gyms', 'Gym')

    for gym in Gym.objects.all():
        numero = 1000
        for socio in Socio.objects.filter(gym=gym, numero_socio__isnull=True).order_by('creado_en', 'id'):
            socio.numero_socio = numero
            socio.save(update_fields=['numero_socio'])
            numero += 1


def revertir(apps, schema_editor):
    # No hay nada que deshacer: quitar el número no recupera ningún dato perdido,
    # y dejarlo evita que un rollback deje huecos si se vuelve a aplicar.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('socios', '0008_socio_numero_socio_socio_numero_socio_unico_por_gym'),
    ]

    operations = [
        migrations.RunPython(asignar_numeros, revertir),
    ]
