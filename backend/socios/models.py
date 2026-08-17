import calendar
from datetime import timedelta

from django.db import models
from django.utils import timezone
from gyms.models import Gym, Sucursal

# Días que un socio puede pagar tarde sin perder su día de corte. Pasados estos, el
# siguiente pago cuenta como reinscripción y el ancla se mueve al día en que pagó.
DIAS_GRACIA_REINSCRIPCION = 30


def sumar_meses(fecha, meses):
    """Suma meses conservando el día del mes, recortando al último día si no existe.

    El 31 de enero + 1 mes es el 28 de febrero, no el 3 de marzo. Y el mes siguiente
    vuelve al 31: el ancla es el día original, no el recortado, así que un socio que se
    inscribió un día 31 no se va corriendo hacia atrás un día por cada febrero.
    """
    mes_total = fecha.month - 1 + meses
    anio = fecha.year + mes_total // 12
    mes = mes_total % 12 + 1
    dia = min(fecha.day, calendar.monthrange(anio, mes)[1])
    return fecha.replace(year=anio, month=mes, day=dia)


class Plan(models.Model):
    TIPO_CHOICES = [
        ('mensual', 'Mensual'),
        ('trimestral', 'Trimestral'),
        ('semestral', 'Semestral'),
        ('anual', 'Anual'),
        ('visita', 'Visita Suelta'),
        ('clases', 'Paquete de Clases'),
    ]

    # Los planes recurrentes se cobran por mes de calendario, no por número de días:
    # así el socio conserva su día de corte (se inscribió un 24, paga los 24). Los que
    # no están aquí (visita, clases) caen a duracion_dias.
    MESES_POR_TIPO = {'mensual': 1, 'trimestral': 3, 'semestral': 6, 'anual': 12}

    gym = models.ForeignKey(Gym, on_delete=models.CASCADE, related_name='planes')
    nombre = models.CharField(max_length=100)
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES)
    precio = models.DecimalField(max_digits=10, decimal_places=2)
    duracion_dias = models.PositiveIntegerField(null=True, blank=True)
    num_clases = models.PositiveIntegerField(null=True, blank=True)
    activo = models.BooleanField(default=True)

    class Meta:
        db_table = 'planes'

    def __str__(self):
        return f'{self.nombre} - ${self.precio}'

    @property
    def es_recurrente(self):
        return self.tipo in self.MESES_POR_TIPO

    def avanzar_periodo(self, desde):
        """Devuelve la fecha de fin de un período que arranca en `desde`.

        None significa membresía sin vencimiento (plan sin duración configurada).
        """
        if self.es_recurrente:
            return sumar_meses(desde, self.MESES_POR_TIPO[self.tipo])
        if self.duracion_dias:
            return desde + timedelta(days=self.duracion_dias)
        return None


class Socio(models.Model):
    SEXO_CHOICES = [('M', 'Masculino'), ('F', 'Femenino'), ('O', 'Otro')]

    gym = models.ForeignKey(Gym, on_delete=models.CASCADE, related_name='socios')
    nombre = models.CharField(max_length=150)
    apellido = models.CharField(max_length=150)
    email = models.EmailField(blank=True)
    telefono = models.CharField(max_length=20, blank=True)
    fecha_nacimiento = models.DateField(null=True, blank=True)
    sexo = models.CharField(max_length=1, choices=SEXO_CHOICES, blank=True)
    foto = models.ImageField(upload_to='socios/fotos/', null=True, blank=True)
    activo = models.BooleanField(default=True)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'socios'

    def __str__(self):
        return f'{self.nombre} {self.apellido}'


class MembresiaQuerySet(models.QuerySet):
    def vigentes(self, hoy=None):
        """Membresías que hoy dan derecho a entrar.

        Definición única de "vigente" para todo el sistema: la usan el serializer de
        Socios y el check-in del kiosco. Mientras vivan en un solo lugar no pueden
        volver a divergir (una pantalla diciendo que el socio está al corriente
        mientras la puerta lo rechaza).
        """
        hoy = hoy or timezone.localdate()
        return self.filter(
            estado='activa',
            fecha_inicio__lte=hoy,
        ).filter(
            models.Q(fecha_fin__gte=hoy) | models.Q(fecha_fin__isnull=True)
        )

    def caducadas(self, hoy=None):
        """Marcadas como activas pero con la fecha ya pasada."""
        hoy = hoy or timezone.localdate()
        return self.filter(estado='activa', fecha_fin__lt=hoy)


class Membresia(models.Model):
    ESTADO_CHOICES = [
        ('activa', 'Activa'),
        ('vencida', 'Vencida'),
        ('suspendida', 'Suspendida'),
        ('pendiente_pago', 'Pendiente de Pago'),
    ]

    objects = MembresiaQuerySet.as_manager()

    socio = models.ForeignKey(Socio, on_delete=models.CASCADE, related_name='membresias')
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT, related_name='membresias')
    sucursal = models.ForeignKey(Sucursal, on_delete=models.PROTECT, related_name='membresias')
    fecha_inicio = models.DateField()
    fecha_fin = models.DateField(null=True, blank=True)
    clases_restantes = models.PositiveIntegerField(null=True, blank=True)
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='pendiente_pago')
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'membresias'

    def __str__(self):
        return f'{self.socio} - {self.plan} ({self.estado})'

    def renovar(self, hoy=None):
        """Aplica un pago: activa la membresía y recorre el período.

        La fecha de cobro es fija por socio: quien se inscribió un 24 paga los 24, y
        adelantar el pago al 19 no le quita esos 5 días. Por eso el período se cuenta
        desde `fecha_fin` (donde quedó), no desde hoy.

        La excepción es el moroso: si lleva más de DIAS_GRACIA_REINSCRIPCION vencido no
        se le arrastran los meses que no vino — se le trata como alta nueva y su día de
        corte pasa a ser el día en que volvió.
        """
        hoy = hoy or timezone.localdate()

        if self.fecha_fin is None:
            # Nunca tuvo vencimiento (o el plan no lo define): se ancla a hoy.
            ancla = hoy
            self.fecha_inicio = hoy
        elif self.fecha_fin < hoy - timedelta(days=DIAS_GRACIA_REINSCRIPCION):
            ancla = hoy
            self.fecha_inicio = hoy
        else:
            # Al corriente o dentro de la gracia: conserva su día de corte.
            ancla = self.fecha_fin

        self.fecha_fin = self.plan.avanzar_periodo(ancla)
        if self.plan.num_clases:
            self.clases_restantes = self.plan.num_clases
        self.estado = 'activa'
        self.save()
        return self


class Pago(models.Model):
    METODO_CHOICES = [
        ('efectivo', 'Efectivo'),
        ('tarjeta', 'Tarjeta'),
        ('transferencia', 'Transferencia'),
    ]

    membresia = models.ForeignKey(Membresia, on_delete=models.CASCADE, related_name='pagos')
    monto = models.DecimalField(max_digits=10, decimal_places=2)
    metodo = models.CharField(max_length=20, choices=METODO_CHOICES)
    referencia = models.CharField(max_length=100, blank=True)
    fecha = models.DateTimeField(auto_now_add=True)
    registrado_por = models.ForeignKey(
        'usuarios.Usuario', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='pagos_registrados'
    )

    class Meta:
        db_table = 'pagos'

    def __str__(self):
        return f'${self.monto} - {self.membresia.socio}'


class Gasto(models.Model):
    CATEGORIA_CHOICES = [
        ('renta', 'Renta'),
        ('nomina', 'Nómina'),
        ('equipo', 'Equipo'),
        ('servicios', 'Servicios'),
        ('mantenimiento', 'Mantenimiento'),
        ('marketing', 'Marketing'),
        ('otro', 'Otro'),
    ]

    gym = models.ForeignKey(Gym, on_delete=models.CASCADE, related_name='gastos')
    categoria = models.CharField(max_length=30, choices=CATEGORIA_CHOICES)
    descripcion = models.CharField(max_length=255)
    monto = models.DecimalField(max_digits=10, decimal_places=2)
    fecha = models.DateField()
    registrado_por = models.ForeignKey(
        'usuarios.Usuario', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='gastos_registrados'
    )

    class Meta:
        db_table = 'gastos'

    def __str__(self):
        return f'{self.categoria} - ${self.monto} ({self.fecha})'
