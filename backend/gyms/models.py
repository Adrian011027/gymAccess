from django.db import models


class Gym(models.Model):
    TIPO_CHOICES = [
        ('box', 'Box / Artes Marciales'),
        ('pesas', 'Gym de Pesas'),
        ('mixto', 'Mixto'),
    ]

    # Qué pasa cuando un socio se presenta en una sucursal que no es la suya. No hay
    # una respuesta universal: hay gyms donde la membresía es de un local concreto y
    # otros donde da lo mismo, así que lo decide el dueño.
    POLITICA_CHOICES = [
        ('libre', 'Puede entrar a cualquier sucursal'),
        # No pide contraseña: quien está en el mostrador pulsa "Autorizar" y su
        # nombre queda en la bitácora. El control es a posteriori, no en la puerta.
        ('autorizacion', 'Recepción decide caso por caso'),
        ('bloqueado', 'Solo su sucursal'),
    ]

    nombre = models.CharField(max_length=200)
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, default='mixto')
    logo = models.ImageField(upload_to='gyms/logos/', null=True, blank=True)
    telefono = models.CharField(max_length=20, blank=True)
    email_contacto = models.EmailField(blank=True)
    politica_visitantes = models.CharField(
        max_length=20, choices=POLITICA_CHOICES, default='libre',
        help_text='Qué hacer si un socio se presenta en una sucursal distinta a la suya',
    )
    direccion = models.TextField(blank=True)
    # Horario de atención por día, con los descansos (cierres parciales) dentro del
    # turno. Estructura validada en GymSerializer:
    #   {"lun": {"abierto": true, "inicio": "05:30", "fin": "22:00",
    #            "descansos": [{"inicio": "13:00", "fin": "15:00"}]}, ...}
    # Es JSON y no un modelo aparte porque se lee y se guarda siempre completo, como
    # una sola preferencia del gym: siete filas nunca se consultan por separado.
    horario = models.JSONField(default=dict, blank=True)
    activo = models.BooleanField(default=True)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'gyms'

    def __str__(self):
        return self.nombre


class Sucursal(models.Model):
    gym = models.ForeignKey(Gym, on_delete=models.CASCADE, related_name='sucursales')
    nombre = models.CharField(max_length=200)
    direccion = models.TextField(blank=True)
    telefono = models.CharField(max_length=20, blank=True)
    activa = models.BooleanField(default=True)

    class Meta:
        db_table = 'sucursales'

    def __str__(self):
        return f'{self.gym.nombre} - {self.nombre}'


class Clase(models.Model):
    TIPO_CHOICES = [
        ('resistencia', 'Resistencia'),
        ('fisico', 'Físico'),
        ('combinaciones', 'Combinaciones'),
        ('defensa', 'Defensa'),
        ('sparring', 'Sparring'),
    ]
    NIVEL_CHOICES = [
        ('principiante', 'Principiante'),
        ('intermedio', 'Intermedio'),
        ('avanzado', 'Avanzado'),
        ('todos', 'Todos'),
    ]

    gym = models.ForeignKey(Gym, on_delete=models.CASCADE, related_name='clases')
    # Nulo = se imparte en todas las sucursales. Un horario y un profesor suelen ser de
    # un local concreto, pero hay clases que se replican, así que no se obliga.
    sucursal = models.ForeignKey(
        Sucursal, on_delete=models.CASCADE,
        null=True, blank=True, related_name='clases'
    )
    nombre = models.CharField(max_length=150)
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES)
    profesor = models.CharField(max_length=150)
    hora_inicio = models.TimeField()
    hora_fin = models.TimeField()
    dias = models.CharField(max_length=100)
    cupo_max = models.PositiveIntegerField(default=20)
    inscritos = models.PositiveIntegerField(default=0)
    nivel = models.CharField(max_length=20, choices=NIVEL_CHOICES, default='todos')
    descripcion = models.TextField(blank=True)
    activa = models.BooleanField(default=True)

    class Meta:
        db_table = 'clases'

    def __str__(self):
        return f'{self.nombre} - {self.profesor}'


class Equipamiento(models.Model):
    CATEGORIA_CHOICES = [
        ('impacto', 'Impacto'),
        ('infraestructura', 'Infraestructura'),
        ('proteccion', 'Protección'),
        ('cardio', 'Cardio'),
        ('piso', 'Piso'),
        ('pesas', 'Pesas'),
    ]

    gym = models.ForeignKey(Gym, on_delete=models.CASCADE, related_name='equipamientos')
    # Nulo = no asignado a un local. `ubicacion` sigue siendo el detalle fino
    # ("bodega", "área de ring"); esto es de qué sucursal es el inventario.
    sucursal = models.ForeignKey(
        Sucursal, on_delete=models.CASCADE,
        null=True, blank=True, related_name='equipamientos'
    )
    nombre = models.CharField(max_length=200)
    categoria = models.CharField(max_length=20, choices=CATEGORIA_CHOICES)
    cantidad = models.PositiveIntegerField(default=1)
    ultima_revision = models.DateField(null=True, blank=True)
    ubicacion = models.CharField(max_length=150, blank=True)
    activo = models.BooleanField(default=True)

    class Meta:
        db_table = 'equipamiento'

    def __str__(self):
        return self.nombre
