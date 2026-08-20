"""Documentos legales y evidencia de su aceptación.

La LFPDPPP pone la carga de la prueba sobre el responsable: no basta con haber
mostrado un aviso de privacidad, hay que poder demostrar *qué versión* aceptó cada
socio y *cuándo*. Por eso el texto se versiona y nunca se edita en sitio: publicar
un cambio crea una versión nueva, y los consentimientos ya otorgados siguen
apuntando a la que el socio realmente leyó.
"""

from django.db import models
from django.utils import timezone

from gyms.models import Gym
from socios.models import Socio


class DocumentoLegal(models.Model):
    AVISO_PRIVACIDAD = 'aviso_privacidad'
    TERMINOS_SERVICIO = 'terminos_servicio'
    CONVENIO_ENCARGADO = 'convenio_encargado'

    TIPO_CHOICES = [
        (AVISO_PRIVACIDAD, 'Aviso de Privacidad (gym → socios)'),
        (TERMINOS_SERVICIO, 'Términos y Condiciones del software (proveedor → gym)'),
        (CONVENIO_ENCARGADO, 'Convenio de Encargado del tratamiento'),
    ]

    # Nulo = documento del proveedor del software, igual para todos los gyms (los
    # términos del servicio y el convenio de encargado). Con gym = documento de ese
    # negocio, típicamente su aviso de privacidad, que redacta y firma él.
    gym = models.ForeignKey(
        Gym, on_delete=models.CASCADE,
        null=True, blank=True, related_name='documentos_legales',
    )
    tipo = models.CharField(max_length=30, choices=TIPO_CHOICES)
    version = models.CharField(
        max_length=20,
        help_text='Etiqueta visible para el usuario, p. ej. "1.0" o "2026-08".',
    )
    titulo = models.CharField(max_length=200)
    contenido = models.TextField(help_text='Texto del documento en Markdown.')
    vigente_desde = models.DateField(default=timezone.localdate)
    activo = models.BooleanField(default=True)
    creado_en = models.DateTimeField(auto_now_add=True)
    publicado_por = models.ForeignKey(
        'usuarios.Usuario', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='documentos_publicados',
    )

    class Meta:
        db_table = 'documentos_legales'
        ordering = ['-vigente_desde', '-id']
        constraints = [
            models.UniqueConstraint(
                fields=['gym', 'tipo', 'version'], name='documento_version_unica',
            ),
        ]

    def __str__(self):
        return f'{self.get_tipo_display()} v{self.version}'

    @classmethod
    def vigente(cls, tipo, gym_id=None, hoy=None):
        """El documento que hay que mostrar hoy, o None si aún no se publica ninguno.

        Se compara contra `vigente_desde` para poder dejar preparada una versión
        futura sin que empiece a exigirse antes de tiempo.
        """
        hoy = hoy or timezone.localdate()
        return cls.objects.filter(
            tipo=tipo, gym_id=gym_id, activo=True, vigente_desde__lte=hoy,
        ).order_by('-vigente_desde', '-id').first()


class ConsentimientoSocio(models.Model):
    """Evidencia de que un socio (o su tutor) aceptó una versión del aviso.

    Es lo único que convierte el aviso en una defensa: sin registro de quién
    aceptó qué y cuándo, publicar el texto no prueba nada.
    """

    OTORGANTE_CHOICES = [
        ('socio', 'El propio socio'),
        ('tutor', 'Padre, madre o tutor (socio menor de edad)'),
    ]
    MEDIO_CHOICES = [
        ('mostrador', 'Aceptado en mostrador ante recepción'),
        ('digital', 'Aceptado por el socio en línea'),
    ]

    socio = models.ForeignKey(Socio, on_delete=models.CASCADE, related_name='consentimientos')
    documento = models.ForeignKey(
        DocumentoLegal, on_delete=models.PROTECT, related_name='consentimientos',
    )
    otorgado_por = models.CharField(max_length=10, choices=OTORGANTE_CHOICES, default='socio')
    medio = models.CharField(max_length=15, choices=MEDIO_CHOICES, default='mostrador')
    # Copia del tutor tal como estaba al firmar: si después cambia de tutor, la
    # evidencia debe seguir diciendo quién aceptó aquel día.
    tutor_nombre = models.CharField(max_length=200, blank=True)
    tutor_parentesco = models.CharField(max_length=50, blank=True)
    aceptado_en = models.DateTimeField(auto_now_add=True)
    ip = models.GenericIPAddressField(null=True, blank=True)
    capturado_por = models.ForeignKey(
        'usuarios.Usuario', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='consentimientos_capturados',
    )

    class Meta:
        db_table = 'consentimientos_socio'
        ordering = ['-aceptado_en']

    def __str__(self):
        return f'{self.socio} aceptó {self.documento}'


class AceptacionUsuario(models.Model):
    """Aceptación de los términos del software por parte del personal del gym.

    Quien acepta en nombre del negocio es el admin; que quede registrado es lo que
    respalda al proveedor si después se discute qué se había pactado.
    """

    usuario = models.ForeignKey(
        'usuarios.Usuario', on_delete=models.CASCADE, related_name='aceptaciones_legales',
    )
    documento = models.ForeignKey(
        DocumentoLegal, on_delete=models.PROTECT, related_name='aceptaciones',
    )
    aceptado_en = models.DateTimeField(auto_now_add=True)
    ip = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=300, blank=True)

    class Meta:
        db_table = 'aceptaciones_usuario'
        ordering = ['-aceptado_en']
        constraints = [
            models.UniqueConstraint(
                fields=['usuario', 'documento'], name='aceptacion_usuario_unica',
            ),
        ]

    def __str__(self):
        return f'{self.usuario} aceptó {self.documento}'
