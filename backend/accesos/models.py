import secrets

from django.db import models
from socios.models import Socio, Membresia
from gyms.models import Sucursal


def generar_token_qr(socio_id):
    """Código de acceso de un socio.

    La parte aleatoria sale de `secrets`, no de `random`: el formato anterior era
    `R3B-QR-{id:05d}-{random.randint(1000,9999)}`, o sea **9 000 combinaciones** por
    socio sobre un id secuencial, y con un generador que no es criptográfico. Con el
    código impreso en la credencial a la vista, adivinar el de otro socio era
    cuestión de intentar.

    Vive aquí porque la misma línea estaba copiada en `AsignarQRView`,
    `SocioViewSet.perform_create` y el comando de siembra: tres sitios que tenían que
    cambiar a la vez y ninguno sabía de los otros.
    """
    return f'R3B-QR-{socio_id:05d}-{secrets.token_urlsafe(12)}'


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
