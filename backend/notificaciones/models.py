from django.db import models


class Notificacion(models.Model):
    TIPO_CHOICES = [
        ('pago_vencido', 'Pago Vencido'),
        ('inventario', 'Inventario'),
        ('membresia_por_vencer', 'Membresía por Vencer'),
        ('socio_nuevo', 'Socio Nuevo'),
        ('otro', 'Otro'),
    ]

    gym = models.ForeignKey('gyms.Gym', on_delete=models.CASCADE, related_name='notificaciones')
    tipo = models.CharField(max_length=30, choices=TIPO_CHOICES, default='otro')
    mensaje = models.CharField(max_length=255)
    link = models.CharField(max_length=255, blank=True)
    leida = models.BooleanField(default=False)
    archivada = models.BooleanField(default=False)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'notificaciones'
        ordering = ['-creado_en']

    def __str__(self):
        return f'{self.tipo} - {self.mensaje}'
