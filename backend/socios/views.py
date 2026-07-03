from rest_framework import viewsets, permissions
from .models import Plan, Socio, Membresia, Pago, Gasto
from .serializers import (
    PlanSerializer, SocioSerializer, MembresiaSerializer,
    PagoSerializer, GastoSerializer
)


class PlanViewSet(viewsets.ModelViewSet):
    serializer_class = PlanSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Plan.objects.filter(gym_id=self.request.user.gym_id, activo=True)


class SocioViewSet(viewsets.ModelViewSet):
    serializer_class = SocioSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Socio.objects.filter(gym_id=self.request.user.gym_id)


class MembresiaViewSet(viewsets.ModelViewSet):
    serializer_class = MembresiaSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Membresia.objects.filter(socio__gym_id=self.request.user.gym_id).select_related('socio', 'plan')


class PagoViewSet(viewsets.ModelViewSet):
    serializer_class = PagoSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Pago.objects.filter(membresia__socio__gym_id=self.request.user.gym_id)

    def perform_create(self, serializer):
        serializer.save(registrado_por=self.request.user)


class GastoViewSet(viewsets.ModelViewSet):
    serializer_class = GastoSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Gasto.objects.filter(gym_id=self.request.user.gym_id)

    def perform_create(self, serializer):
        serializer.save(gym_id=self.request.user.gym_id, registrado_por=self.request.user)
