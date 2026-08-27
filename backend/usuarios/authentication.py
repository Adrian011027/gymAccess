"""Autenticación JWT que además comprueba que el gimnasio siga operativo.

Suspender a un cliente es la única palanca de cobranza del panel del SaaS, y no
cortaba nada: `Gym.activo = False` solo sacaba al gimnasio de
`GymViewSet.get_queryset`. Todos los demás ViewSets filtran por `gym_id` sin mirar
`gym.activo`, así que con el gym suspendido recepción seguía listando socios (200)
y seguía entrando por el login (200). Lo único que perdía el moroso era su pantalla
de configuración.

**Por qué aquí y no en un permiso.** El sitio evidente sería
`DEFAULT_PERMISSION_CLASSES`, pero no sirve: media docena de vistas declaran
`permission_classes = [permissions.IsAuthenticated]` de forma explícita, y eso
*reemplaza* al default en vez de sumarse. La regla viviría en el ajuste global y no
se aplicaría justo donde importa. La autenticación, en cambio, corre antes que
cualquier permiso y no la puede pisar una vista.

El superadmin del SaaS no tiene gym y por eso nunca queda fuera: es quien tiene que
poder entrar a reactivar al cliente que acaba de pagar.
"""

from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.authentication import JWTAuthentication

from gyms.models import Gym


class JWTUsuarioOperativo(JWTAuthentication):
    def get_user(self, validated_token):
        usuario = super().get_user(validated_token)
        gym_id = getattr(usuario, 'gym_id', None)
        if gym_id is not None and not Gym.objects.filter(id=gym_id, activo=True).exists():
            # 401 y no 403: el token es válido pero la cuenta detrás ya no puede
            # operar, que es lo mismo que le pasa a un usuario dado de baja. Así el
            # frontend lo trata por el camino que ya tiene para sesión inválida.
            raise AuthenticationFailed(
                'El gimnasio está suspendido. Contacta al proveedor del sistema.',
                code='gym_suspendido',
            )
        return usuario
