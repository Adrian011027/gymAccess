from django.core.management.base import BaseCommand

from usuarios.eliminacion import RETENCION_DIAS, eliminados_para_purgar, purgar_eliminados


class Command(BaseCommand):
    help = f'Borra definitivamente los empleados eliminados hace más de {RETENCION_DIAS} días'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Solo cuenta cuántos se borrarían, sin borrar nada.',
        )

    def handle(self, *args, **opciones):
        if opciones['dry_run']:
            total = eliminados_para_purgar().count()
            self.stdout.write(f'{total} empleados se borrarían (eliminados hace más de {RETENCION_DIAS} días)')
            return
        total = purgar_eliminados()
        self.stdout.write(self.style.SUCCESS(
            f'{total} empleados borrados definitivamente (eliminados hace más de {RETENCION_DIAS} días)'
        ))
