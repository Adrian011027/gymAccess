from django.db import models
from django.utils import timezone
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from .eliminacion import purgar_eliminados
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
        # Un empleado eliminado no existe para el sistema, ni siquiera con
        # `incluir_bajas`: no se lista, no se consulta y no se edita (404). Su fila
        # espera 30 días antes de borrarse (usuarios/eliminacion.py).
        vigentes = Usuario.objects.filter(eliminado_en__isnull=True)
        qs = vigentes.filter(is_active=True)
        if self.request.query_params.get('incluir_bajas') == '1':
            qs = vigentes
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

    def _liberar_correo(self, serializer):
        # El correo de un eliminado sigue ocupando el UNIQUE hasta que se purga: se
        # purga ya para que el alta o el cambio de correo no choquen con él.
        email = serializer.validated_data.get('email')
        if email:
            purgar_eliminados(email=email)

    def perform_create(self, serializer):
        self._liberar_correo(serializer)
        if self.request.user.rol != 'superadmin':
            serializer.save(gym_id=self.request.user.gym_id)
        else:
            serializer.save()

    def perform_update(self, serializer):
        self._liberar_correo(serializer)
        serializer.save()

    def perform_destroy(self, instance):
        """Eliminación del empleado: inmediata para el sistema, definitiva a los 30 días.

        No se borra la fila en el acto: `Pago.registrado_por`, `Acceso.autorizado_por` y
        el resto apuntan aquí con SET_NULL, y el mes de margen permite notar un error
        antes de perder quién registró cada movimiento. Mientras tanto no puede iniciar
        sesión (is_active) ni aparece en ningún listado (eliminado_en). La purga está en
        `usuarios/eliminacion.py`.
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
        instance.eliminado_en = timezone.now()
        instance.save(update_fields=['is_active', 'eliminado_en'])

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
