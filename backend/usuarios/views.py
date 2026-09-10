from django.db import models
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from .models import Usuario
from .permissions import ROLES_ADMIN, EsAdminGym
from .serializers import UsuarioSerializer, LoginSerializer


class LoginView(TokenObtainPairView):
    serializer_class = LoginSerializer
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'login'


class RefreshView(TokenRefreshView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'login'


class UsuarioViewSet(viewsets.ModelViewSet):
    serializer_class = UsuarioSerializer
    permission_classes = [permissions.IsAuthenticated, EsAdminGym]

    def get_queryset(self):
        user = self.request.user
        # Los dados de baja se ocultan: siguen en la base porque de ellos cuelga la
        # bitácora (quién autorizó qué), pero no son personal en activo.
        qs = Usuario.objects.filter(is_active=True)
        if self.request.query_params.get('incluir_bajas') == '1':
            qs = Usuario.objects.all()
        if user.rol == 'superadmin':
            return qs
        qs = qs.filter(gym_id=user.gym_id)

        # `?sucursal=<id>` para que el dueño mire la plantilla de un local concreto.
        # Va a mano y no con SucursalScopedMixin porque un empleado se filtra por las
        # sucursales donde PUEDE trabajar, no solo por la activa de su sesión: con
        # `sucursal_id` a secas, quien rota entre locales desaparecía del listado de
        # los demás según dónde hubiera entrado esa mañana.
        #
        # Al admin, que no tiene sucursal, no se le esconde: es de todas.
        sucursal = self.request.query_params.get('sucursal')
        if sucursal:
            try:
                sucursal_id = int(sucursal)
            except (TypeError, ValueError):
                raise ValidationError({'sucursal': 'Sucursal inválida.'})
            qs = qs.filter(
                models.Q(sucursal_id=sucursal_id)
                | models.Q(sucursales_permitidas__id=sucursal_id)
                | models.Q(rol__in=ROLES_ADMIN)
            ).distinct()
        return qs

    def perform_create(self, serializer):
        if self.request.user.rol != 'superadmin':
            serializer.save(gym_id=self.request.user.gym_id)
        else:
            serializer.save()

    def perform_destroy(self, instance):
        """Baja lógica del empleado.

        No se borra la fila: `Pago.registrado_por`, `AjusteMembresia.autorizado_por` y
        `Acceso.autorizado_por` apuntan aquí con SET_NULL, así que un DELETE real
        dejaría la bitácora sin responsable justo en los movimientos que existen para
        poder auditar a alguien. Desactivado no puede iniciar sesión, que es el efecto
        que se busca.
        """
        usuario = self.request.user
        if instance.id == usuario.id:
            raise ValidationError(
                {'detail': 'No puedes darte de baja a ti mismo. Pídeselo a otro admin.'}
            )
        if instance.rol in ROLES_ADMIN:
            # Quedarse sin ningún admin deja el gym sin quien administre nada, y
            # tampoco quien pueda reactivar al que se acaba de dar de baja.
            quedan = Usuario.objects.filter(
                gym_id=instance.gym_id, rol__in=ROLES_ADMIN, is_active=True,
            ).exclude(id=instance.id).exists()
            if not quedan:
                raise ValidationError(
                    {'detail': 'Es el último administrador del gym: nombra otro antes '
                               'de darlo de baja.'}
                )
        instance.is_active = False
        instance.save(update_fields=['is_active'])

    def get_permissions(self):
        # Cambiar de sucursal activa es sobre uno mismo, no un endpoint de admin:
        # recepción con 2+ sucursales permitidas lo usa para elegir con cuál entra.
        if self.action == 'sucursal_activa':
            return [permissions.IsAuthenticated()]
        return super().get_permissions()

    @action(detail=False, methods=['post'], url_path='sucursal-activa')
    def sucursal_activa(self, request):
        user = request.user
        sucursal = user.sucursales_permitidas.filter(id=request.data.get('sucursal')).first()
        if sucursal is None:
            return Response(
                {'sucursal': 'Debe ser una de tus sucursales permitidas.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        user.sucursal = sucursal
        user.save(update_fields=['sucursal'])
        token = LoginSerializer.get_token(user)
        return Response({'access': str(token.access_token), 'refresh': str(token)})
