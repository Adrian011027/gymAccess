from django.db import models


class AccesoSoporte(models.Model):
    """Bitácora de cada vez que el dueño del SaaS entra como un gimnasio.

    Emitir un token a nombre de otra persona es la operación más delicada del panel:
    quien la usa ve datos personales de socios que no son suyos. Sin registro no hay
    manera de responder "quién entró a Round3Boxing el martes y para qué", que es
    justo lo que un cliente tiene derecho a preguntar —y lo que la LFPDPPP espera que
    el responsable del tratamiento pueda demostrar—.

    Mismo criterio que `AjusteMembresia`: la operación se permite, pero deja rastro.
    """

    gym = models.ForeignKey(
        'gyms.Gym', on_delete=models.CASCADE, related_name='accesos_soporte',
    )
    # SET_NULL y no CASCADE: si algún día se borra la cuenta del superadmin, el
    # registro de que alguien entró debe sobrevivir. Un rastro que se borra solo
    # con quitar al autor no es un rastro.
    superadmin = models.ForeignKey(
        'usuarios.Usuario', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='soportes_iniciados',
    )
    suplantado = models.ForeignKey(
        'usuarios.Usuario', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='soportes_recibidos',
    )
    motivo = models.CharField(max_length=255, blank=True)
    ip = models.GenericIPAddressField(null=True, blank=True)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'accesos_soporte'
        ordering = ['-creado_en']

    def __str__(self):
        return f'{self.superadmin} -> {self.gym} ({self.creado_en:%Y-%m-%d %H:%M})'
