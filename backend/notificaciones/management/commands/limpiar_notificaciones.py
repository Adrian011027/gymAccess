from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from notificaciones.models import Notificacion

RETENCION_DIAS = 15


class Command(BaseCommand):
    help = f'Elimina notificaciones con más de {RETENCION_DIAS} días de antigüedad'

    def handle(self, *args, **options):
        limite = timezone.now() - timedelta(days=RETENCION_DIAS)
        total, _ = Notificacion.objects.filter(creado_en__lt=limite).delete()
        self.stdout.write(self.style.SUCCESS(f'{total} notificaciones eliminadas (más de {RETENCION_DIAS} días)'))
