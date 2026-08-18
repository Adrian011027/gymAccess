from django.db import migrations


def asignar_sucursal(apps, schema_editor):
    """Le pone sucursal base a los socios que ya existen.

    Se toma la de su última membresía: es donde firmaron, así que es la respuesta
    correcta. Quien no tenga membresía se queda en NULL, que significa "de ninguna en
    particular" y el check-in lo deja pasar a cualquiera.
    """
    Socio = apps.get_model('socios', 'Socio')
    Membresia = apps.get_model('socios', 'Membresia')

    for socio in Socio.objects.filter(sucursal__isnull=True):
        membresia = (
            Membresia.objects
            .filter(socio_id=socio.id)
            .order_by('-fecha_inicio', '-id')
            .first()
        )
        if membresia and membresia.sucursal_id:
            socio.sucursal_id = membresia.sucursal_id
            socio.save(update_fields=['sucursal'])


def revertir(apps, schema_editor):
    apps.get_model('socios', 'Socio').objects.update(sucursal=None)


class Migration(migrations.Migration):

    dependencies = [
        ('socios', '0004_socio_sucursal'),
    ]

    operations = [
        migrations.RunPython(asignar_sucursal, revertir),
    ]
