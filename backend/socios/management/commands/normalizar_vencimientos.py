from datetime import date, datetime, timedelta

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from gyms.models import Gym, Sucursal
from socios.models import AjusteMembresia, Membresia, Plan, Socio
from usuarios.models import Usuario
from usuarios.permissions import ROLES_ADMIN

MOTIVO = 'Normalización masiva de vencimientos'


class Command(BaseCommand):
    help = (
        'Empuja a una fecha común el vencimiento de las membresías que quedaron atrás, '
        'y da de alta una membresía a los socios que no tienen ninguna. '
        'Cada cambio queda registrado en AjusteMembresia.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--fecha', required=True, help='Nuevo vencimiento, formato AAAA-MM-DD')
        parser.add_argument('--plan', default='Regular', help='Plan para socios sin membresía (default: Regular)')
        parser.add_argument('--gym', help='Nombre del gym; por defecto, todos')
        parser.add_argument(
            '--incluir-suspendidas', action='store_true',
            help='También reactiva las suspendidas (por defecto se respetan)',
        )
        parser.add_argument(
            '--incluir-vigentes', action='store_true',
            help='También adelanta las que aún están vigentes pero vencen antes de --fecha '
                 '(les regala días: por defecto se dejan como están)',
        )
        parser.add_argument('--dry-run', action='store_true', help='Muestra el plan sin escribir nada')

    def handle(self, *args, **opts):
        try:
            objetivo = datetime.strptime(opts['fecha'], '%Y-%m-%d').date()
        except ValueError:
            raise CommandError('--fecha debe tener formato AAAA-MM-DD (ej. 2026-08-15)')

        gyms = Gym.objects.all()
        if opts['gym']:
            gyms = gyms.filter(nombre=opts['gym'])
            if not gyms.exists():
                raise CommandError(f'No existe el gym "{opts["gym"]}"')

        dry = opts['dry_run']
        hoy = timezone.localdate()
        estados = ['activa', 'vencida'] + (['suspendida'] if opts['incluir_suspendidas'] else [])

        for gym in gyms:
            self.stdout.write(self.style.MIGRATE_HEADING(f'\n=== {gym.nombre} ==='))
            autorizador = Usuario.objects.filter(
                gym=gym, rol__in=ROLES_ADMIN, is_active=True,
            ).order_by('id').first()
            if autorizador is None and not dry:
                self.stdout.write(self.style.WARNING(
                    '  Sin admin activo: los ajustes quedarán sin autorizado_por.'
                ))

            self._altas(gym, objetivo, opts['plan'], dry, autorizador, hoy)
            self._empujar(gym, objetivo, estados, dry, autorizador, hoy, opts['incluir_vigentes'])
            self._reportar_omitidos(gym, objetivo, opts['incluir_suspendidas'])

        if dry:
            self.stdout.write(self.style.WARNING('\n(dry-run: no se escribió nada)'))

    # --- socios sin ninguna membresía -------------------------------------------------

    def _altas(self, gym, objetivo, nombre_plan, dry, autorizador, hoy):
        huerfanos = Socio.objects.filter(gym=gym, membresias__isnull=True, activo=True)
        if not huerfanos.exists():
            self.stdout.write('  Socios sin membresía: 0')
            return

        plan = Plan.objects.filter(gym=gym, nombre=nombre_plan).first()
        sucursal = Sucursal.objects.filter(gym=gym, activa=True).order_by('id').first()
        if plan is None or sucursal is None:
            falta = 'plan ' + nombre_plan if plan is None else 'sucursal activa'
            self.stdout.write(self.style.ERROR(
                f'  {huerfanos.count()} socios sin membresía, pero no hay {falta}: se omiten.'
            ))
            return

        self.stdout.write(f'  Alta de "{plan.nombre}" con vencimiento {objetivo}:')
        for socio in huerfanos:
            self.stdout.write(f'    + {socio.nombre} {socio.apellido}')
            if dry:
                continue
            with transaction.atomic():
                membresia = Membresia.objects.create(
                    socio=socio, plan=plan, sucursal=sucursal,
                    fecha_inicio=hoy, fecha_fin=objetivo, estado='activa',
                    clases_restantes=plan.num_clases,
                )
                AjusteMembresia.objects.create(
                    membresia=membresia,
                    fecha_anterior=None, fecha_nueva=objetivo,
                    estado_anterior='', estado_nuevo='activa',
                    motivo=f'{MOTIVO} (alta con plan {plan.nombre})',
                    autorizado_por=autorizador,
                )

    # --- membresías con el vencimiento atrasado ---------------------------------------

    def _empujar(self, gym, objetivo, estados, dry, autorizador, hoy, incluir_vigentes):
        """Solo se adelantan las que quedaron atrás.

        Nunca se acorta una membresía: quien ya vence después de la fecha objetivo se
        queda como está, o normalizar le estaría quitando días pagados.

        Por defecto tampoco se tocan las que siguen vigentes aunque venzan antes de la
        fecha objetivo: adelantarlas es regalar días que nadie pidió regalar.
        """
        from django.db.models import Q

        qs = Membresia.objects.filter(
            socio__gym=gym, estado__in=estados,
        ).filter(
            Q(fecha_fin__lt=objetivo) | Q(fecha_fin__isnull=True)
        ).select_related('socio', 'plan').order_by('socio__nombre')

        if not incluir_vigentes:
            vigentes = Membresia.objects.vigentes(hoy).values_list('id', flat=True)
            respetadas = qs.filter(id__in=list(vigentes)).select_related('socio')
            for m in respetadas:
                self.stdout.write(
                    f'    · {m.socio.nombre} {m.socio.apellido} sigue vigente hasta {m.fecha_fin}: '
                    f'sin cambios (usa --incluir-vigentes para adelantarla).'
                )
            qs = qs.exclude(id__in=list(vigentes))

        if not qs.exists():
            self.stdout.write('  Membresías a adelantar: 0')
            return

        self.stdout.write(f'  Vencimiento -> {objetivo}:')
        for m in qs:
            self.stdout.write(
                f'    ~ {m.socio.nombre} {m.socio.apellido:<12} {m.plan.nombre:<11} '
                f'{str(m.fecha_fin):<12} [{m.estado}] -> {objetivo} [activa]'
            )
            if dry:
                continue
            with transaction.atomic():
                anterior_fecha, anterior_estado = m.fecha_fin, m.estado
                m.fecha_fin = objetivo
                m.estado = 'activa'
                m.save(update_fields=['fecha_fin', 'estado'])
                AjusteMembresia.objects.create(
                    membresia=m,
                    fecha_anterior=anterior_fecha, fecha_nueva=objetivo,
                    estado_anterior=anterior_estado, estado_nuevo='activa',
                    motivo=MOTIVO,
                    autorizado_por=autorizador,
                )

    # --- lo que se deja fuera a propósito ---------------------------------------------

    def _reportar_omitidos(self, gym, objetivo, incluir_suspendidas):
        omitidas = Membresia.objects.filter(
            socio__gym=gym, estado='pendiente_pago',
        ).select_related('socio')
        if not incluir_suspendidas:
            omitidas = omitidas | Membresia.objects.filter(
                socio__gym=gym, estado='suspendida',
            ).select_related('socio')

        for m in omitidas:
            self.stdout.write(self.style.WARNING(
                f'    ! {m.socio.nombre} {m.socio.apellido} sin tocar: estado "{m.estado}" '
                f'(vence {m.fecha_fin}). Activarla daría acceso sin pago.'
            ))

        tarde = Membresia.objects.filter(
            socio__gym=gym, estado='activa', fecha_fin__gt=objetivo,
        ).count()
        if tarde:
            self.stdout.write(f'    · {tarde} membresías ya vencen después de {objetivo}: sin cambios.')
