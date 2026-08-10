import random
from datetime import timedelta

from django.utils import timezone
from rest_framework import viewsets, permissions
from rest_framework.exceptions import ValidationError
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
        gym_id = self.request.user.gym_id
        if not gym_id:
            # Un superadmin sin gym debe decir explícitamente en qué gym da de alta;
            # Socio.gym es NOT NULL, así que guardar sin gym revienta en el INSERT.
            gym = serializer.validated_data.get('gym')
            if not gym:
                raise ValidationError(
                    {'gym': 'El usuario no tiene gym asignado: indica el gym del socio.'}
                )
            gym_id = gym.id
        socio = serializer.save(gym_id=gym_id)
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

    def _validar_pertenencia(self, serializer):
        """El queryset de lectura ya filtra por gym, pero la escritura no validaba nada:
        un POST con socio/plan/sucursal de otro negocio se guardaba con 201 y quedaba
        invisible para quien lo creó. Mismo patrón que PagoViewSet.perform_create.
        """
        gym_id = self.request.user.gym_id
        errores = {}
        for campo, mensaje in (
            ('socio', 'Socio no encontrado'),
            ('plan', 'Plan no encontrado'),
            ('sucursal', 'Sucursal no encontrada'),
        ):
            obj = serializer.validated_data.get(campo)
            if obj is not None and obj.gym_id != gym_id:
                errores[campo] = mensaje
        if errores:
            raise ValidationError(errores)

    def perform_create(self, serializer):
        self._validar_pertenencia(serializer)
        serializer.save()

    def perform_update(self, serializer):
        self._validar_pertenencia(serializer)
        serializer.save()


class PagoViewSet(viewsets.ModelViewSet):
    serializer_class = PagoSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Pago.objects.filter(membresia__socio__gym_id=self.request.user.gym_id)

    def perform_create(self, serializer):
        membresia = serializer.validated_data.get('membresia')
        if not membresia or membresia.socio.gym_id != self.request.user.gym_id:
            raise ValidationError({'membresia': 'Membresía no encontrada'})

        pago = serializer.save(registrado_por=self.request.user)

        # El pago reactiva la membresía y recorre el período según el plan
        plan = membresia.plan
        hoy = timezone.localdate()
        membresia.fecha_inicio = hoy
        membresia.fecha_fin = hoy + timedelta(days=plan.duracion_dias) if plan.duracion_dias else None
        if plan.num_clases:
            membresia.clases_restantes = plan.num_clases
        membresia.estado = 'activa'
        membresia.save()
        return pago


class GastoViewSet(viewsets.ModelViewSet):
    serializer_class = GastoSerializer
    permission_classes = [permissions.IsAuthenticated, EsAdminGym]

    def get_queryset(self):
        return Gasto.objects.filter(gym_id=self.request.user.gym_id)

    def perform_create(self, serializer):
        serializer.save(gym_id=self.request.user.gym_id, registrado_por=self.request.user)
