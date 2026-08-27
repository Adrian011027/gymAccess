from django.db.models import Q
from rest_framework import viewsets, permissions
from rest_framework.exceptions import ValidationError
from usuarios.permissions import AdminOSoloLectura, EsAdminGym
from usuarios.scoping import SucursalScopedMixin
from notificaciones.models import Notificacion
from .models import Gym, Sucursal, Clase, Equipamiento
from .serializers import GymSerializer, SucursalSerializer, ClaseSerializer, EquipamientoSerializer


class GymViewSet(viewsets.ModelViewSet):
    """El gimnasio se edita desde aquí, pero no se crea ni se borra.

    Dar de alta un gimnasio es dar de alta un *cliente del SaaS*: eso vive en
    `/api/saas/tenants/`, que además crea su sucursal y su admin en la misma
    transacción. Abierto aquí, el admin de un gym podía sembrar gimnasios sueltos
    en la tabla de clientes.
    """

    serializer_class = GymSerializer
    permission_classes = [permissions.IsAuthenticated, AdminOSoloLectura]
    # Sin 'delete' ni 'post': de un Gym cuelgan en cascada sucursales, socios,
    # membresías, pagos, accesos y usuarios. El panel del SaaS ya prohíbe este
    # DELETE y responde que se suspenda, citando los cinco años que el CFF obliga a
    # conservar los pagos (`saas/views.py`) —pero la puerta del inquilino se había
    # quedado abierta, y es la que usaría un cliente enfadado: verificado, devolvía
    # 204 y se llevaba el gimnasio entero—.
    http_method_names = ['get', 'put', 'patch', 'head', 'options']

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

    def perform_create(self, serializer):
        """El gym lo pone el servidor, no el cliente.

        `get_queryset` filtraba la lectura por gym pero nadie miraba la escritura:
        un POST con `gym` ajeno se guardaba con 201 en el negocio de al lado y
        desaparecía de la lista de quien lo creó. Mismo patrón que
        `MembresiaViewSet._validar_pertenencia`, que ya lo resolvía para socio/plan.
        """
        gym_id = self._gym_destino(serializer)
        serializer.save(gym_id=gym_id)

    def perform_update(self, serializer):
        # Una sucursal no se muda de gimnasio: sin esto, el PATCH es la misma
        # escritura cruzada que cierra `perform_create`, solo que en dos pasos.
        serializer.save(gym_id=serializer.instance.gym_id)

    def _gym_destino(self, serializer):
        if self.request.user.rol == 'superadmin':
            gym = serializer.validated_data.get('gym')
            if gym is None:
                raise ValidationError(
                    {'gym': 'Indica el gimnasio: tu usuario no está atado a ninguno.'}
                )
            return gym.id
        return self.request.user.gym_id

    def perform_destroy(self, instance):
        """Baja lógica: de una sucursal cuelgan accesos, ventas y membresías con
        PROTECT, y el histórico de caja tiene que seguir cuadrando."""
        instance.activa = False
        instance.save(update_fields=['activa'])


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
