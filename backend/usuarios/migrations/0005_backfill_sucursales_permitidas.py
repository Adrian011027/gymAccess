from django.db import migrations


def asignar_permitidas(apps, schema_editor):
    """Quien ya tenía una sucursal activa, la conserva como su única permitida.

    Sin esto, al desplegar el M2M vacío, un recepcionista con `sucursal` fija
    dejaría de tener ninguna opción listada para elegir al cambiar de sucursal.
    """
    Usuario = apps.get_model('usuarios', 'Usuario')
    for usuario in Usuario.objects.filter(sucursal__isnull=False):
        usuario.sucursales_permitidas.add(usuario.sucursal_id)


def revertir(apps, schema_editor):
    apps.get_model('usuarios', 'Usuario').sucursales_permitidas.through.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('usuarios', '0004_usuario_sucursales_permitidas_horario'),
    ]

    operations = [
        migrations.RunPython(asignar_permitidas, revertir),
    ]
