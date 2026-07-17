import random

from rest_framework import viewsets, permissions
from accesos.models import MetodoAcceso
from usuarios.permissions import AdminOSoloLectura, EsAdminGym
from .models import Plan, Socio, Membresia, Pago, Gasto
from .serializers import (
    PlanSerializer, SocioSerializer, MembresiaSerializer,
    PagoSerializer, GastoSerializer
)


class PlanViewSet(viewsets.ModelViewSet):
    serializer_class = PlanSerializer
    permission_classes = [permissions.IsAuthenticated, AdminOSoloLectura]

    def get_queryset(self):
        return Plan.objects.filter(gym_id=self.request.user.gym_id, activo=True)


class SocioViewSet(viewsets.ModelViewSet):
    serializer_class = SocioSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Socio.objects.filter(
            gym_id=self.request.user.gym_id
        ).prefetch_related('metodos_acceso')

    def perform_create(self, serializer):
        if self.request.user.gym_id:
            socio = serializer.save(gym_id=self.request.user.gym_id)
        else:
            socio = serializer.save()
        # Cada socio nuevo recibe su código de acceso automáticamente
        MetodoAcceso.objects.create(
            socio=socio,
            tipo='qr',
            token=f'R3B-QR-{socio.id:05d}-{random.randint(1000, 9999)}',
        )


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
    permission_classes = [permissions.IsAuthenticated, EsAdminGym]

    def get_queryset(self):
        return Gasto.objects.filter(gym_id=self.request.user.gym_id)

    def perform_create(self, serializer):
        serializer.save(gym_id=self.request.user.gym_id, registrado_por=self.request.user)
