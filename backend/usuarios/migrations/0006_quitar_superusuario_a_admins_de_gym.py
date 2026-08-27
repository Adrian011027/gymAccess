"""Quita los permisos de Django a quien no es el dueño del SaaS.

Hallazgo 7 de la auditoría del 2026-08-23. En la base había esto:

    admin@admin.com          rol=superadmin  gym=None  is_staff=True  is_superuser=True
    diego@round3boxing.com   rol=admin       gym=1     is_staff=True  is_superuser=True

`is_superuser=True` en el dueño de **un** gimnasio le da `/admin/` sobre todos los
modelos de **todos** los inquilinos, saltándose entera la capa de permisos de la API:
el scoping por gym, los `EsAdminGym`, todo. Y `PermissionsMixin` hace que cualquier
comprobación de permisos de Django devuelva True para él.

`rol` (el campo del dominio) y `is_superuser` (el de Django) son cosas distintas que
se habían quedado pegadas por cómo se sembraron las cuentas. Aquí se separan: solo el
superadmin del SaaS conserva los dos.

Reversible: `is_staff` no se puede restituir por rol —no hay dato de quién lo tenía
antes— así que la vuelta atrás no lo devuelve. Es deliberado: reactivarlo a ciegas
volvería a abrir el agujero.
"""

from django.db import migrations


def quitar_superusuario(apps, schema_editor):
    Usuario = apps.get_model('usuarios', 'Usuario')
    Usuario.objects.exclude(rol='superadmin').update(is_staff=False, is_superuser=False)


def volver_atras(apps, schema_editor):
    # A propósito no hace nada. Ver el docstring.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('usuarios', '0005_backfill_sucursales_permitidas'),
    ]

    operations = [
        migrations.RunPython(quitar_superusuario, volver_atras),
    ]
