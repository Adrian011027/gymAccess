"""
Puebla la base de datos con datos de demostración para Round3Boxing.

Uso:
    python manage.py seed_demo

Es idempotente: borra los datos de demo previos y los vuelve a crear,
así puedes correrlo las veces que quieras antes de una presentación.
"""
import random
from datetime import timedelta, time, datetime

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from gyms.models import Gym, Sucursal, Clase, Equipamiento
from usuarios.models import Usuario
from socios.models import Plan, Socio, Membresia, Pago, Gasto
from accesos.models import MetodoAcceso, Acceso


class Command(BaseCommand):
    help = 'Puebla la base de datos con datos de demo para Round3Boxing'

    @transaction.atomic
    def handle(self, *args, **options):
        self.stdout.write('Limpiando datos de demo previos...')
        # Orden inverso a las dependencias
        Acceso.objects.all().delete()
        MetodoAcceso.objects.all().delete()
        Pago.objects.all().delete()
        Membresia.objects.all().delete()
        Socio.objects.all().delete()
        Gasto.objects.all().delete()
        Plan.objects.all().delete()
        Clase.objects.all().delete()
        Equipamiento.objects.all().delete()
        Sucursal.objects.all().delete()
        Gym.objects.all().delete()

        hoy = timezone.now().date()

        # ---------------- Gimnasio ----------------
        gym = Gym.objects.create(
            nombre='Round3Boxing',
            tipo='box',
            telefono='55 1234 5678',
            email_contacto='contacto@round3boxing.com',
            activo=True,
        )
        self.stdout.write(self.style.SUCCESS(f'Gym creado: {gym.nombre}'))

        sucursal = Sucursal.objects.create(
            gym=gym,
            nombre='Matriz Centro',
            direccion='Av. Reforma 123, Col. Centro, CDMX',
            telefono='55 1234 5678',
            activa=True,
        )

        # ---------------- Usuarios / staff ----------------
        # Diego: dueño del negocio
        diego = Usuario.objects.filter(email='diego@round3boxing.com').first()
        if diego:
            diego.delete()
        diego = Usuario.objects.create_user(
            email='diego@round3boxing.com',
            password='Diego1234',
            nombre='Diego',
            rol='admin',
            gym=gym,
            is_staff=True,
            is_superuser=True,
        )
        self.stdout.write(self.style.SUCCESS(
            'Dueño creado: Diego  (login: diego@round3boxing.com / Diego1234)'
        ))

        # Recepcionista
        recep = Usuario.objects.filter(email='recepcion@round3boxing.com').first()
        if recep:
            recep.delete()
        Usuario.objects.create_user(
            email='recepcion@round3boxing.com',
            password='Recepcion123',
            nombre='Marisol Vega',
            rol='recepcion',
            gym=gym,
        )

        # ---------------- Planes ----------------
        planes_data = [
            ('Regular', 'mensual', 499.00, 30),
            ('Estudiante', 'mensual', 399.00, 30),
            ('Pareja', 'mensual', 899.00, 30),
            ('3 Meses', 'trimestral', 1349.00, 90),
            ('Anual', 'anual', 4999.00, 365),
        ]
        planes = {}
        for nombre, tipo, precio, dias in planes_data:
            planes[nombre] = Plan.objects.create(
                gym=gym,
                nombre=nombre,
                tipo=tipo,
                precio=precio,
                duracion_dias=dias,
                activo=True,
            )
        plan = planes['Regular']
        self.stdout.write(self.style.SUCCESS(f'{len(planes)} planes creados: {", ".join(planes)}'))

        # ---------------- Socios ----------------
        socios_data = [
            ('Carlos', 'Ramírez', 'M', 'carlos.ramirez@gmail.com', '55 8100 2233', 1994),
            ('Ana', 'Torres', 'F', 'ana.torres@gmail.com', '55 8100 4455', 1998),
            ('Luis', 'Hernández', 'M', 'luis.hdz@gmail.com', '55 8100 6677', 1990),
            ('Sofía', 'Martínez', 'F', 'sofia.mtz@gmail.com', '55 8100 8899', 2001),
            ('Miguel', 'González', 'M', 'miguel.glz@gmail.com', '55 8101 1122', 1987),
            ('Valentina', 'López', 'F', 'valentina.lopez@gmail.com', '55 8101 3344', 1996),
            ('Jorge', 'Sánchez', 'M', 'jorge.sanchez@gmail.com', '55 8101 5566', 1992),
            ('Daniela', 'Flores', 'F', 'daniela.flores@gmail.com', '55 8101 7788', 1999),
            ('Roberto', 'Díaz', 'M', 'roberto.diaz@gmail.com', '55 8101 9900', 1985),
            ('Fernanda', 'Cruz', 'F', 'fernanda.cruz@gmail.com', '55 8102 1234', 2000),
            ('Andrés', 'Morales', 'M', 'andres.morales@gmail.com', '55 8102 5678', 1993),
            ('Paola', 'Reyes', 'F', 'paola.reyes@gmail.com', '55 8102 9012', 1997),
            ('Emiliano', 'Ortiz', 'M', 'emiliano.ortiz@gmail.com', '55 8103 3456', 1995),
            ('Regina', 'Castillo', 'F', 'regina.castillo@gmail.com', '55 8103 7890', 2002),
            ('Héctor', 'Mendoza', 'M', 'hector.mendoza@gmail.com', '55 8104 1234', 1989),
        ]

        metodos_pago = ['efectivo', 'tarjeta', 'transferencia']
        plan_ciclo = list(planes.values())
        socios = []
        for i, (nombre, apellido, sexo, email, tel, anio) in enumerate(socios_data):
            socio = Socio.objects.create(
                gym=gym,
                nombre=nombre,
                apellido=apellido,
                email=email,
                telefono=tel,
                fecha_nacimiento=datetime(anio, random.randint(1, 12), random.randint(1, 28)).date(),
                sexo=sexo,
                activo=True,
            )
            socios.append(socio)
            plan_socio = plan_ciclo[i % len(plan_ciclo)]

            # Método de acceso (QR) para cada socio
            MetodoAcceso.objects.create(
                socio=socio,
                tipo='qr',
                token=f'R3B-QR-{socio.id:05d}-{random.randint(1000, 9999)}',
                activo=True,
            )

            # Definir estado de la membresía para variar el panel
            # La mayoría activas; algunas vencidas / pendientes
            duracion = plan_socio.duracion_dias or 30
            if i % 7 == 5:
                estado = 'vencida'
                inicio = hoy - timedelta(days=duracion + 15)
                fin = hoy - timedelta(days=15)
            elif i % 7 == 6:
                estado = 'pendiente_pago'
                inicio = hoy
                fin = hoy + timedelta(days=duracion)
            else:
                estado = 'activa'
                dias_transcurridos = random.randint(1, min(25, duracion - 1) if duracion > 1 else 1)
                inicio = hoy - timedelta(days=dias_transcurridos)
                fin = inicio + timedelta(days=duracion)

            membresia = Membresia.objects.create(
                socio=socio,
                plan=plan_socio,
                sucursal=sucursal,
                fecha_inicio=inicio,
                fecha_fin=fin,
                estado=estado,
            )

            # Pago si la membresía no está pendiente
            if estado != 'pendiente_pago':
                Pago.objects.create(
                    membresia=membresia,
                    monto=plan_socio.precio,
                    metodo=random.choice(metodos_pago),
                    referencia=f'PAGO-{membresia.id:05d}',
                    registrado_por=diego,
                )

            # Accesos recientes (solo para membresías activas)
            if estado == 'activa':
                for _ in range(random.randint(2, 8)):
                    dias_atras = random.randint(0, 20)
                    ts = timezone.now() - timedelta(days=dias_atras, hours=random.randint(6, 21))
                    acc = Acceso.objects.create(
                        socio=socio,
                        sucursal=sucursal,
                        membresia=membresia,
                        metodo_usado='qr',
                        resultado='permitido',
                    )
                    Acceso.objects.filter(pk=acc.pk).update(timestamp=ts)

        # Un par de accesos denegados (membresías vencidas) para mostrar el flujo
        for socio in socios:
            memb = socio.membresias.first()
            if memb and memb.estado == 'vencida':
                acc = Acceso.objects.create(
                    socio=socio,
                    sucursal=sucursal,
                    membresia=memb,
                    metodo_usado='qr',
                    resultado='denegado',
                    motivo_denegado='membresia_vencida',
                )
                Acceso.objects.filter(pk=acc.pk).update(
                    timestamp=timezone.now() - timedelta(days=1, hours=3)
                )

        self.stdout.write(self.style.SUCCESS(f'{len(socios)} socios creados con membresías, pagos y accesos'))

        # ---------------- Inventario / Equipamiento ----------------
        equipo = [
            ('Ring de boxeo profesional', 'infraestructura', 1, 'Área central'),
            ('Costal pesado 40kg', 'impacto', 8, 'Zona de sacos'),
            ('Costal pesado 30kg', 'impacto', 6, 'Zona de sacos'),
            ('Pera de velocidad', 'impacto', 6, 'Muro norte'),
            ('Pera loca (doble anclaje)', 'impacto', 3, 'Muro norte'),
            ('Guantes de boxeo 12oz', 'proteccion', 20, 'Bodega / renta'),
            ('Guantes de boxeo 16oz', 'proteccion', 15, 'Bodega / renta'),
            ('Manoplas de entrenamiento (pares)', 'impacto', 10, 'Estante coaches'),
            ('Vendas para manos (pares)', 'proteccion', 40, 'Recepción'),
            ('Protectores bucales', 'proteccion', 25, 'Recepción'),
            ('Caretas de sparring', 'proteccion', 8, 'Zona de ring'),
            ('Petos / protector de torso', 'proteccion', 6, 'Zona de ring'),
            ('Cuerdas para saltar', 'cardio', 20, 'Zona funcional'),
            ('Colchonetas / tatami', 'piso', 30, 'Zona funcional'),
            ('Mancuernas (set 2-20kg)', 'pesas', 12, 'Zona de fuerza'),
            ('Balones medicinales', 'cardio', 8, 'Zona funcional'),
            ('Espejos de pared', 'infraestructura', 6, 'Muro sur'),
        ]
        for nombre, categoria, cantidad, ubicacion in equipo:
            Equipamiento.objects.create(
                gym=gym,
                nombre=nombre,
                categoria=categoria,
                cantidad=cantidad,
                ubicacion=ubicacion,
                ultima_revision=hoy - timedelta(days=random.randint(5, 60)),
                activo=True,
            )
        self.stdout.write(self.style.SUCCESS(f'{len(equipo)} artículos de inventario creados'))

        # ---------------- Clases ----------------
        clases = [
            ('Boxeo Principiantes', 'fisico', 'Diego Fuentes', time(7, 0), time(8, 0),
             'Lun,Mié,Vie', 20, 'principiante', 'Fundamentos: guardia, desplazamientos y jab.'),
            ('Acondicionamiento Físico', 'resistencia', 'Marisol Vega', time(8, 0), time(9, 0),
             'Lun,Mié,Vie', 25, 'todos', 'Cardio y fuerza orientado al boxeo.'),
            ('Técnica y Combinaciones', 'combinaciones', 'Diego Fuentes', time(18, 0), time(19, 30),
             'Mar,Jue', 18, 'intermedio', 'Combinaciones y trabajo de manoplas.'),
            ('Defensa Personal', 'defensa', 'Roberto Lara', time(19, 0), time(20, 0),
             'Mar,Jue', 15, 'todos', 'Bloqueos, esquivas y reacción.'),
            ('Sparring Controlado', 'sparring', 'Diego Fuentes', time(20, 0), time(21, 0),
             'Vie', 12, 'avanzado', 'Combate controlado con equipo de protección.'),
        ]
        for nombre, tipo, prof, hi, hf, dias, cupo, nivel, desc in clases:
            Clase.objects.create(
                gym=gym,
                nombre=nombre,
                tipo=tipo,
                profesor=prof,
                hora_inicio=hi,
                hora_fin=hf,
                dias=dias,
                cupo_max=cupo,
                inscritos=random.randint(cupo // 2, cupo),
                nivel=nivel,
                descripcion=desc,
                activa=True,
            )
        self.stdout.write(self.style.SUCCESS(f'{len(clases)} clases creadas'))

        # ---------------- Gastos ----------------
        gastos = [
            ('renta', 'Renta del local - mes en curso', 18000, 3),
            ('nomina', 'Nómina coaches y recepción', 24000, 5),
            ('servicios', 'Luz, agua e internet', 4200, 8),
            ('equipo', 'Reposición de vendas y protectores bucales', 2800, 12),
            ('mantenimiento', 'Mantenimiento de ring y costales', 1500, 20),
            ('marketing', 'Campaña en redes sociales', 3000, 15),
        ]
        for categoria, desc, monto, dias_atras in gastos:
            Gasto.objects.create(
                gym=gym,
                categoria=categoria,
                descripcion=desc,
                monto=monto,
                fecha=hoy - timedelta(days=dias_atras),
                registrado_por=diego,
            )
        self.stdout.write(self.style.SUCCESS(f'{len(gastos)} gastos creados'))

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('=== Demo de Round3Boxing lista ==='))
        self.stdout.write('Dueño (admin):   diego@round3boxing.com  /  Diego1234')
        self.stdout.write('Recepción:       recepcion@round3boxing.com  /  Recepcion123')
