from django.db import models
from django.utils import timezone
from gyms.models import Gym, Sucursal


class Plan(models.Model):
    TIPO_CHOICES = [
        ('mensual', 'Mensual'),
        ('trimestral', 'Trimestral'),
        ('semestral', 'Semestral'),
        ('anual', 'Anual'),
        ('visita', 'Visita Suelta'),
        ('clases', 'Paquete de Clases'),
    ]

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
