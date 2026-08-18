from django.db import migrations

ROLES_ADMIN = ('admin', 'superadmin')


def asignar_sucursal(apps, schema_editor):
    """Ata al personal operativo a su sucursal cuando no hay ambigüedad.

    Si el gym tiene exactamente una sucursal, la respuesta es única y se asigna. Con
    varias no se adivina: quedan en NULL (ven todo el gym, como hasta ahora) y el
    dueño los asigna a mano. Es el default seguro: nadie pierde acceso de golpe.

    Los admins se dejan siempre en NULL: NULL es justamente "ve todo el gym".
    """
    Usuario = apps.get_model('usuarios', 'Usuario')
    Sucursal = apps.get_model('gyms', 'Sucursal')

    for usuario in Usuario.objects.filter(sucursal__isnull=True, gym__isnull=False):
        if usuario.rol in ROLES_ADMIN:
            continue
        sucursales = list(Sucursal.objects.filter(gym_id=usuario.gym_id, activa=True)[:2])
        if len(sucursales) == 1:
            usuario.sucursal_id = sucursales[0].id
            usuario.save(update_fields=['sucursal'])


def revertir(apps, schema_editor):
    apps.get_model('usuarios', 'Usuario').objects.update(sucursal=None)


class Migration(migrations.Migration):

    dependencies = [
        ('usuarios', '0002_usuario_sucursal'),
        ('gyms', '0003_gym_politica_visitantes'),
    ]

    operations = [
        migrations.RunPython(asignar_sucursal, revertir),
    ]
