from django.db import migrations, models
from django.utils import timezone


def fechar_bajas_existentes(apps, schema_editor):
    """Los empleados dados de baja antes de este cambio no tenían fecha.

    Hasta ahora la única vía que apagaba `is_active` en un usuario de gym era la baja
    desde Empleados, así que esos son eliminados. Se les pone la fecha de hoy: su mes
    empieza a contar desde el despliegue, no se borran de golpe al migrar.
    """
    Usuario = apps.get_model('usuarios', 'Usuario')
    Usuario.objects.filter(
        is_active=False, gym__isnull=False, eliminado_en__isnull=True,
    ).update(eliminado_en=timezone.now())


class Migration(migrations.Migration):

    dependencies = [
        ('usuarios', '0006_quitar_superusuario_a_admins_de_gym'),
    ]

    operations = [
        migrations.AddField(
            model_name='usuario',
            name='eliminado_en',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.RunPython(fechar_bajas_existentes, migrations.RunPython.noop),
    ]
