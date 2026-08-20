"""Publica los documentos del proveedor desde los borradores de `legal/`.

Los términos del servicio y el convenio de encargado no los edita ningún gym desde
la aplicación: son del proveedor y valen igual para todos, así que se cargan desde
el repositorio y no desde una pantalla.
"""

from pathlib import Path

from django.core.management.base import BaseCommand

from legal.models import DocumentoLegal

ARCHIVOS = {
    DocumentoLegal.TERMINOS_SERVICIO: (
        'terminos-servicio.md', 'Términos y Condiciones de Uso del Software',
    ),
    DocumentoLegal.CONVENIO_ENCARGADO: (
        'convenio-encargado.md', 'Convenio de Encargado del Tratamiento de Datos',
    ),
}


class Command(BaseCommand):
    help = 'Publica los términos del servicio y el convenio de encargado desde legal/*.md'

    def add_arguments(self, parser):
        # No se llama --version: Django ya reserva ese argumento para el suyo.
        parser.add_argument(
            '--ver', default='1.0',
            help='Etiqueta de versión a publicar (por defecto 1.0).',
        )
        parser.add_argument(
            '--dir', default=None,
            help='Carpeta con los .md (por defecto legal/ en la raíz del proyecto).',
        )

    def handle(self, *args, **opciones):
        version = opciones['ver']
        raiz = Path(opciones['dir']) if opciones['dir'] else Path(__file__).resolve().parents[4] / 'legal'

        if not raiz.is_dir():
            self.stderr.write(self.style.ERROR(f'No existe la carpeta {raiz}'))
            return

        for tipo, (archivo, titulo) in ARCHIVOS.items():
            ruta = raiz / archivo
            if not ruta.exists():
                self.stderr.write(self.style.WARNING(f'Falta {ruta}, se omite.'))
                continue

            # gym=None: son del proveedor, no de un negocio concreto.
            if DocumentoLegal.objects.filter(gym=None, tipo=tipo, version=version).exists():
                self.stdout.write(f'{titulo} v{version} ya existe, se omite.')
                continue

            DocumentoLegal.objects.create(
                gym=None, tipo=tipo, version=version, titulo=titulo,
                contenido=ruta.read_text(encoding='utf-8'),
            )
            self.stdout.write(self.style.SUCCESS(f'Publicado: {titulo} v{version}'))

        self.stdout.write(
            '\nRecuerda: son borradores. Revísalos con un abogado antes de operar con ellos.'
        )
