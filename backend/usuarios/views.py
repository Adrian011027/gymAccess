from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from .models import Usuario
from .permissions import EsAdminGym
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
        if user.rol == 'superadmin':
            return Usuario.objects.all()
        return Usuario.objects.filter(gym_id=user.gym_id)

    def perform_create(self, serializer):
        if self.request.user.rol != 'superadmin':
            serializer.save(gym_id=self.request.user.gym_id)
        else:
            serializer.save()

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
