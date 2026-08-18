"""Alcance por sucursal.

Un usuario con `sucursal` asignada solo ve y solo escribe en esa sucursal. Un usuario
sin sucursal (el dueño) ve todo su gym.

Vive en un solo archivo a propósito: la versión copiada en cada `get_queryset` es como
el filtrado por gym terminó divergiendo entre lectura y escritura, y un POST con la
sucursal de al lado se guardaba con 201.
"""

from rest_framework.exceptions import ValidationError


class SucursalScopedMixin:
    """Acota un ViewSet a la sucursal del usuario.

    `sucursal_lookup` es la ruta del ORM desde el modelo hasta Sucursal, para modelos
    que la tienen indirecta (un Pago la alcanza vía `membresia__sucursal`).
    """

    sucursal_lookup = 'sucursal'

    @property
    def sucursal_id(self):
        return getattr(self.request.user, 'sucursal_id', None)

    def sucursal_solicitada(self):
        """`?sucursal=<id>` del dueño para mirar un local concreto.

        Solo se atiende a quien no está atado a una sucursal: a recepción se le ignora,
        porque si no el filtro sería un modo de salirse de su alcance escribiendo la
        query a mano.
        """
        if self.sucursal_id is not None:
            return None
        valor = self.request.query_params.get('sucursal')
        if not valor:
            return None
        from gyms.models import Sucursal
        try:
            sucursal_id = int(valor)
        except (TypeError, ValueError):
            raise ValidationError({'sucursal': 'Sucursal inválida.'})
        # Aunque el dueño ve todo su gym, sigue sin poder mirar el de otro negocio.
        if not Sucursal.objects.filter(
            id=sucursal_id, gym_id=self.request.user.gym_id,
        ).exists():
            raise ValidationError({'sucursal': 'Sucursal no encontrada.'})
        return sucursal_id

    def scope_sucursal(self, qs):
        objetivo = self.sucursal_id or self.sucursal_solicitada()
        if objetivo is None:
            return qs
        return qs.filter(**{self.sucursal_lookup: objetivo})

    def validar_escritura(self, sucursal):
        """La sucursal a la que se quiere escribir debe ser la del usuario.

        Filtrar la lectura no basta: sin esto, recepción de Norte manda un POST con la
        sucursal de Centro y el registro se guarda donde no debe y desaparece de su
        propia lista.
        """
        self.validar_escritura_id(sucursal.id if sucursal is not None else None)

    def validar_escritura_id(self, sucursal_id):
        propia = self.sucursal_id
        if propia is None:
            return
        if sucursal_id is not None and sucursal_id != propia:
            raise ValidationError(
                {'sucursal': 'Solo puedes registrar movimientos en tu sucursal.'}
            )

    def sucursal_por_defecto(self, sucursal):
        """Devuelve la sucursal a usar: la enviada, o la del usuario si no mandó ninguna."""
        if sucursal is None and self.sucursal_id is not None:
            from gyms.models import Sucursal
            return Sucursal.objects.filter(id=self.sucursal_id).first()
        return sucursal
