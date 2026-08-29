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

    def precio_en(self, sucursal_id):
        """Precio efectivo del plan en una sucursal.

        La mayoría de gyms cobran igual en todos lados y nunca crean filas en
        `PrecioPlanSucursal`, así que el default es `self.precio`. Los que sí varían
        por local (renta distinta por zona, etc.) crean una excepción puntual ahí;
        el resto de sucursales sigue cayendo al precio base.
        """
        if sucursal_id is None:
            return self.precio
        # `precios_sucursal_prefetched` la deja `MembresiaViewSet` con Prefetch()
        # para no pagar una query por membresía al listar; si no está, se consulta.
        overrides = getattr(self, 'precios_sucursal_prefetched', None)
        if overrides is not None:
            for o in overrides:
                if o.sucursal_id == sucursal_id:
                    return o.precio
            return self.precio
        override = self.precios_sucursal.filter(sucursal_id=sucursal_id).first()
        return override.precio if override else self.precio


class PrecioPlanSucursal(models.Model):
    """Excepción de precio: este plan cuesta distinto en esta sucursal puntual.

    Sin filas aquí, `Plan.precio` manda en todas las sucursales — el caso normal.
    Un gym que cobra distinto por local solo agrega las excepciones que necesita,
    no un precio por cada combinación plan×sucursal.
    """
    plan = models.ForeignKey(Plan, on_delete=models.CASCADE, related_name='precios_sucursal')
    sucursal = models.ForeignKey(Sucursal, on_delete=models.CASCADE, related_name='precios_plan')
    precio = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        db_table = 'precios_plan_sucursal'
        unique_together = ('plan', 'sucursal')

    def __str__(self):
        return f'{self.plan.nombre} @ {self.sucursal.nombre}: ${self.precio}'


class SocioQuerySet(models.QuerySet):
    def vivos(self):
        """Los que no están dados de baja lógicamente.

        Definición única de "existe" para todo el sistema, igual que
        `MembresiaQuerySet.vigentes()`: si cada módulo la reescribe, el socio dado de
        baja termina desapareciendo del listado pero siguiendo en el check-in.
        """
        return self.filter(eliminado_en__isnull=True)


class Socio(models.Model):
    SEXO_CHOICES = [('M', 'Masculino'), ('F', 'Femenino'), ('O', 'Otro')]

    gym = models.ForeignKey(Gym, on_delete=models.CASCADE, related_name='socios')
    # Consecutivo por gym, empieza en 1000 (SocioViewSet.perform_create lo asigna).
    # Es el número que recepción dice en voz alta, se imprime y se busca a mano;
    # a propósito NO es el código del QR: ese sigue con su parte aleatoria porque
    # abre la puerta, y un consecutivo ahí se adivina probando números seguidos.
    numero_socio = models.PositiveIntegerField(null=True, blank=True)
    # Dónde está registrado y dónde paga. El socio sigue siendo del gym: toda sucursal
    # puede verlo y atenderlo. Esto solo dice de dónde es, para poder reportarlo y para
    # que el check-in aplique la política de visitantes del gym.
    sucursal = models.ForeignKey(
        Sucursal, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='socios'
    )
    nombre = models.CharField(max_length=150)
    apellido = models.CharField(max_length=150)
    email = models.EmailField(blank=True)
    telefono = models.CharField(max_length=20, blank=True)
    fecha_nacimiento = models.DateField(null=True, blank=True)
    sexo = models.CharField(max_length=1, choices=SEXO_CHOICES, blank=True)
    foto = models.ImageField(upload_to='socios/fotos/', null=True, blank=True)
    # Un menor no puede consentir el tratamiento de sus datos: lo hace quien ejerce
    # la patria potestad. Se piden solo cuando la fecha de nacimiento dice que lo es
    # (lo valida SocioSerializer), no a todo el mundo.
    tutor_nombre = models.CharField(max_length=200, blank=True)
    tutor_parentesco = models.CharField(max_length=50, blank=True)
    tutor_telefono = models.CharField(max_length=20, blank=True)
    activo = models.BooleanField(default=True)
    creado_en = models.DateTimeField(auto_now_add=True)
    # Fecha en que se ejerció el derecho de cancelación (ARCO). Los datos personales
    # se borran, pero el registro sobrevive anonimizado porque de él cuelgan pagos
    # que la obligación fiscal manda conservar.
    anonimizado_en = models.DateTimeField(null=True, blank=True)
    # Baja lógica. NO es lo mismo que `activo=False`: ese es un socio que existe pero
    # no está al corriente, y sigue saliendo en el filtro "Inactivos" del listado.
    # Esto es "se eliminó": desaparece de la interfaz, pero la fila sobrevive porque de
    # ella cuelgan pagos (CFF art. 30 obliga a conservarlos 5 años), consentimientos
    # que prueban el cumplimiento de la LFPDPPP, y la bitácora de accesos. Un DELETE
    # real se llevaba las cuatro cosas por cascada.
    eliminado_en = models.DateTimeField(null=True, blank=True)
    eliminado_por = models.ForeignKey(
        'usuarios.Usuario', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='socios_eliminados',
    )

    objects = SocioQuerySet.as_manager()

    class Meta:
        db_table = 'socios'
        constraints = [
            # Nulo (registros de antes de esta migración sin backfill) no choca
            # consigo mismo: SQL trata cada NULL como distinto de los demás.
            models.UniqueConstraint(fields=['gym', 'numero_socio'], name='numero_socio_unico_por_gym'),
        ]

    def __str__(self):
        return f'{self.nombre} {self.apellido}'

    def edad(self, hoy=None):
        """Edad en años cumplidos, o None si no se capturó la fecha."""
        if not self.fecha_nacimiento:
            return None
        hoy = hoy or timezone.localdate()
        nac = self.fecha_nacimiento
        return hoy.year - nac.year - ((hoy.month, hoy.day) < (nac.month, nac.day))

    @property
    def es_menor(self):
        """None cuando no hay fecha: no se puede afirmar ni que sí ni que no."""
        edad = self.edad()
        return None if edad is None else edad < 18


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


class AjusteMembresia(models.Model):
    """Bitácora de cambios manuales a la fecha de vencimiento.

    Mover esta fecha es regalar tiempo de gimnasio sin cobrarlo, así que cada cambio
    queda registrado: quién lo pidió, quién lo autorizó con su contraseña, desde qué
    fecha, hacia qué fecha y por qué. Sin esto la autorización no sirve de nada:
    nadie podría auditar después quién extendió a quién.
    """

    membresia = models.ForeignKey(Membresia, on_delete=models.CASCADE, related_name='ajustes')
    fecha_anterior = models.DateField(null=True, blank=True)
    fecha_nueva = models.DateField(null=True, blank=True)
    estado_anterior = models.CharField(max_length=20)
    estado_nuevo = models.CharField(max_length=20)
    motivo = models.CharField(max_length=255, blank=True)
    solicitado_por = models.ForeignKey(
        'usuarios.Usuario', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='ajustes_solicitados'
    )
    autorizado_por = models.ForeignKey(
        'usuarios.Usuario', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='ajustes_autorizados'
    )
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'ajustes_membresia'
        ordering = ['-creado_en']

    def __str__(self):
        return f'{self.membresia_id}: {self.fecha_anterior} -> {self.fecha_nueva}'


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

    METODO_CHOICES = [
        ('efectivo', 'Efectivo'),
        ('tarjeta', 'Tarjeta'),
        ('transferencia', 'Transferencia'),
    ]

    gym = models.ForeignKey(Gym, on_delete=models.CASCADE, related_name='gastos')
    # Nulo = gasto del negocio completo (contador, publicidad general). Con sucursal =
    # de ese local, que es lo que permite saber si una sucursal se paga sola.
    sucursal = models.ForeignKey(
        Sucursal, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='gastos'
    )
    categoria = models.CharField(max_length=30, choices=CATEGORIA_CHOICES)
    descripcion = models.CharField(max_length=255)
    monto = models.DecimalField(max_digits=10, decimal_places=2)
    # Con qué se pagó. Sin esto el corte de caja no cuadra: la renta pagada por
    # transferencia no sale del cajón, y restarla del efectivo dejaría a recepción
    # buscando un faltante que nunca existió.
    metodo = models.CharField(max_length=20, choices=METODO_CHOICES, default='efectivo')
    fecha = models.DateField()
    registrado_por = models.ForeignKey(
        'usuarios.Usuario', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='gastos_registrados'
    )

    class Meta:
        db_table = 'gastos'

    def __str__(self):
        return f'{self.categoria} - ${self.monto} ({self.fecha})'
