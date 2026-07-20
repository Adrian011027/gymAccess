from rest_framework import viewsets, permissions
from usuarios.permissions import AdminOSoloLectura, EsAdminGym
from notificaciones.models import Notificacion
from .models import Gym, Sucursal, Clase, Equipamiento
from .serializers import GymSerializer, SucursalSerializer, ClaseSerializer, EquipamientoSerializer


class GymViewSet(viewsets.ModelViewSet):
    serializer_class = GymSerializer
    permission_classes = [permissions.IsAuthenticated, AdminOSoloLectura]

    def get_queryset(self):
        qs = Gym.objects.filter(activo=True)
        if self.request.user.rol == 'superadmin':
            return qs
        return qs.filter(id=self.request.user.gym_id)


class SucursalViewSet(viewsets.ModelViewSet):
    serializer_class = SucursalSerializer
    permission_classes = [permissions.IsAuthenticated, AdminOSoloLectura]

    def get_queryset(self):
        qs = Sucursal.objects.filter(activa=True)
        if self.request.user.rol == 'superadmin':
            return qs
        return qs.filter(gym_id=self.request.user.gym_id)


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
        equipo = serializer.save(gym_id=self.request.user.gym_id)
        Notificacion.objects.create(
            gym_id=self.request.user.gym_id,
            tipo='inventario',
            mensaje=f'Se agregó "{equipo.nombre}" al inventario',
            link='/equipamiento',
        )

    def perform_update(self, serializer):
        equipo = serializer.save()
        Notificacion.objects.create(
            gym_id=equipo.gym_id,
            tipo='inventario',
            mensaje=f'Se actualizó "{equipo.nombre}" en el inventario',
            link='/equipamiento',
        )

    def perform_destroy(self, instance):
        Notificacion.objects.create(
            gym_id=instance.gym_id,
            tipo='inventario',
            mensaje=f'Se eliminó "{instance.nombre}" del inventario',
            link='/equipamiento',
        )
        instance.delete()
