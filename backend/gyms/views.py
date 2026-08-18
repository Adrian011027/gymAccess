from django.db.models import Q
from rest_framework import viewsets, permissions
from usuarios.permissions import AdminOSoloLectura, EsAdminGym
from usuarios.scoping import SucursalScopedMixin
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


class ClaseViewSet(SucursalScopedMixin, viewsets.ModelViewSet):
    serializer_class = ClaseSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = Clase.objects.filter(gym_id=self.request.user.gym_id, activa=True)
        objetivo = self.sucursal_id or self.sucursal_solicitada()
        if objetivo is None:
            return qs
        # Las clases sin sucursal se imparten en todas, así que se ven desde cualquiera.
        return qs.filter(Q(sucursal_id=objetivo) | Q(sucursal__isnull=True))

    def perform_create(self, serializer):
        self.validar_escritura(serializer.validated_data.get('sucursal'))
        extra = {}
        if serializer.validated_data.get('sucursal') is None and self.sucursal_id:
            extra['sucursal_id'] = self.sucursal_id
        serializer.save(gym_id=self.request.user.gym_id, **extra)

    def perform_update(self, serializer):
        self.validar_escritura(serializer.validated_data.get('sucursal'))
        serializer.save()


class EquipamientoViewSet(SucursalScopedMixin, viewsets.ModelViewSet):
    serializer_class = EquipamientoSerializer
    permission_classes = [permissions.IsAuthenticated, EsAdminGym]

    def get_queryset(self):
        qs = Equipamiento.objects.filter(gym_id=self.request.user.gym_id, activo=True)
        objetivo = self.sucursal_id or self.sucursal_solicitada()
        if objetivo is None:
            return qs
        return qs.filter(Q(sucursal_id=objetivo) | Q(sucursal__isnull=True))

    def perform_create(self, serializer):
        self.validar_escritura(serializer.validated_data.get('sucursal'))
        extra = {}
        if serializer.validated_data.get('sucursal') is None and self.sucursal_id:
            extra['sucursal_id'] = self.sucursal_id
        equipo = serializer.save(gym_id=self.request.user.gym_id, **extra)
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
