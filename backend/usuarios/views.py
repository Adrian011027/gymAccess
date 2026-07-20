from rest_framework import viewsets, permissions
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
