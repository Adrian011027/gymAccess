from django.db import models
from socios.models import Socio, Membresia
from gyms.models import Sucursal


class MetodoAcceso(models.Model):
    TIPO_CHOICES = [
        ('qr', 'Código QR'),
        ('huella', 'Huella Digital'),
        ('rfid', 'Tarjeta RFID/NFC'),
        ('manual', 'Manual'),
    ]

    socio = models.ForeignKey(Socio, on_delete=models.CASCADE, related_name='metodos_acceso')
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, default='qr')
    # Para QR: token único. Para huella/RFID: referencia al hardware.
    token = models.CharField(max_length=255, unique=True)
    activo = models.BooleanField(default=True)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'metodos_acceso'

    def __str__(self):
        return f'{self.socio} - {self.tipo}'


class Acceso(models.Model):
    RESULTADO_CHOICES = [
        ('permitido', 'Permitido'),
        ('denegado', 'Denegado'),
    ]

    MOTIVO_DENEGADO_CHOICES = [
        ('membresia_vencida', 'Membresía Vencida'),
        ('sin_membresia', 'Sin Membresía'),
        ('clases_agotadas', 'Clases Agotadas'),
        ('suspendido', 'Suspendido'),
        ('otra_sucursal', 'Pertenece a Otra Sucursal'),
        ('ya_registrado', 'Ya Registró su Acceso Hoy'),
    ]

    socio = models.ForeignKey(Socio, on_delete=models.CASCADE, related_name='accesos')
    sucursal = models.ForeignKey(Sucursal, on_delete=models.PROTECT, related_name='accesos')
    membresia = models.ForeignKey(
        Membresia, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='accesos'
    )
    metodo_usado = models.CharField(max_length=20, default='qr')
    resultado = models.CharField(max_length=20, choices=RESULTADO_CHOICES)
    motivo_denegado = models.CharField(
        max_length=30, choices=MOTIVO_DENEGADO_CHOICES,
        null=True, blank=True
    )
    # Quién autorizó con su contraseña una entrada que de otro modo se habría negado
    # (socio de otra sucursal). Nulo en los accesos normales.
    autorizado_por = models.ForeignKey(
        'usuarios.Usuario', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='accesos_autorizados'
    )
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'accesos'
        indexes = [
            models.Index(fields=['timestamp']),
            models.Index(fields=['socio', 'timestamp']),
            models.Index(fields=['sucursal', 'timestamp']),
        ]

    def __str__(self):
        return f'{self.socio} - {self.resultado} - {self.timestamp}'
