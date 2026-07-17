from rest_framework import viewsets, permissions
from usuarios.permissions import AdminOSoloLectura, EsAdminGym
from .models import Gym, Sucursal, Clase, Equipamiento
from .serializers import GymSerializer, SucursalSerializer, ClaseSerializer, EquipamientoSerializer


class GymViewSet(viewsets.ModelViewSet):
    queryset = Gym.objects.filter(activo=True)
    serializer_class = GymSerializer
    permission_classes = [permissions.IsAuthenticated, AdminOSoloLectura]


class SucursalViewSet(viewsets.ModelViewSet):
    serializer_class = SucursalSerializer
    permission_classes = [permissions.IsAuthenticated, AdminOSoloLectura]

    def get_queryset(self):
        return Sucursal.objects.filter(activa=True)


class ClaseViewSet(viewsets.ModelViewSet):
    serializer_class = ClaseSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Clase.objects.filter(gym_id=self.request.user.gym_id, activa=True)

    def perform_create(self, serializer):
        serializer.save(gym_id=self.request.user.gym_id)


class EquipamientoViewSet(viewsets.ModelViewSet):
    serializer_class = EquipamientoSerializer
    permission_classes = [permissions.IsAuthenticated, EsAdminGym]

    def get_queryset(self):
        return Equipamiento.objects.filter(gym_id=self.request.user.gym_id, activo=True)

    def perform_create(self, serializer):
        serializer.save(gym_id=self.request.user.gym_id)
