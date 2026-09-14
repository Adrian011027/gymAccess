"""Borrado definitivo de los empleados eliminados.

Eliminar a un empleado desde Empleados es inmediato para el sistema: deja de poder
entrar, desaparece del listado y no se le puede consultar ni editar. La fila se queda
30 días (margen para detectar un error antes de que ya no haya vuelta) y después se
borra de verdad.

Qué pasa con lo que registró: los pagos, ventas, gastos, accesos, ajustes y
consentimientos apuntan al empleado con SET_NULL, así que se conservan —los pagos hay
que guardarlos cinco años— pero sin su nombre. Sus aceptaciones de términos se van
con él (CASCADE).
"""

from datetime import timedelta

from django.db import transaction
from django.utils import timezone

RETENCION_DIAS = 30


def eliminados_para_purgar(ahora=None):
    from .models import Usuario
    limite = (ahora or timezone.now()) - timedelta(days=RETENCION_DIAS)
    return Usuario.objects.filter(eliminado_en__isnull=False, eliminado_en__lt=limite)


@transaction.atomic
def purgar_eliminados(ahora=None, email=None):
    """Borra los eliminados con más de 30 días. Devuelve cuántos usuarios borró.

    Con `email` borra además al eliminado que tenga ese correo sin esperar el plazo:
    el correo es único, y sin esto recontratar a alguien fallaría durante un mes con
    "ya existe un usuario" por una cuenta que el sistema dice que no existe.
    """
    from .models import Usuario
    qs = eliminados_para_purgar(ahora)
    if email:
        qs = qs | Usuario.objects.filter(eliminado_en__isnull=False, email__iexact=email)
    ids = list(qs.values_list('id', flat=True))
    if not ids:
        return 0
    Usuario.objects.filter(id__in=ids).delete()
    return len(ids)
