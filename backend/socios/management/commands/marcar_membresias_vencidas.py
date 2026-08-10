from django.core.management.base import BaseCommand
from django.utils import timezone

from socios.models import Membresia


class Command(BaseCommand):
    help = 'Marca como vencidas las membresías cuya fecha_fin ya pasó'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Muestra cuántas se marcarían sin escribir en la base',
        )

    def handle(self, *args, **options):
        hoy = timezone.localdate()
        qs = Membresia.objects.caducadas(hoy)
        total = qs.count()

        if options['dry_run']:
            for m in qs.select_related('socio')[:50]:
                self.stdout.write(f'  {m.socio} — venció {m.fecha_fin}')
            self.stdout.write(self.style.WARNING(f'{total} membresías se marcarían como vencidas (dry-run)'))
            return

        qs.update(estado='vencida')
        self.stdout.write(self.style.SUCCESS(f'{total} membresías marcadas como vencidas'))
