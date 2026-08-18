import random
from datetime import timedelta

from django.db import models, transaction
from django.utils import timezone
from rest_framework import status, viewsets, permissions
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from accesos.models import MetodoAcceso
from usuarios.models import Usuario
from usuarios.permissions import ROLES_ADMIN, AdminOSoloLectura, EsAdminGym
from usuarios.scoping import SucursalScopedMixin
from .models import AjusteMembresia, Plan, Socio, Membresia, Pago, Gasto
from .serializers import (
    AjusteMembresiaSerializer, AjusteVencimientoInputSerializer,
    PlanSerializer, SocioSerializer, MembresiaSerializer,
    PagoSerializer, GastoSerializer
)


class PlanViewSet(viewsets.ModelViewSet):
    serializer_class = PlanSerializer
    permission_classes = [permissions.IsAuthenticated, AdminOSoloLectura]

    def get_queryset(self):
        return Plan.objects.filter(gym_id=self.request.user.gym_id, activo=True)


class SocioViewSet(SucursalScopedMixin, viewsets.ModelViewSet):
    """Los socios NO se acotan por sucursal a propósito.

    El socio le paga al negocio, no al local: si recepción de Norte no pudiera ver al
    socio de Centro que viene de visita, no podría ni buscarlo ni atenderlo. Quién
    puede *entrar* a qué sucursal lo decide la política del gym en el check-in;
    aquí solo se expone de qué sucursal es, para que se note en pantalla.
    """

    serializer_class = SocioSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Socio.objects.filter(
            gym_id=self.request.user.gym_id
        ).select_related('sucursal').prefetch_related('metodos_acceso')

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
        # Un socio dado de alta en una caja se registra en esa sucursal salvo que
        # indiquen otra. El dueño (sin sucursal) sí puede elegirla.
        extra = {}
        if serializer.validated_data.get('sucursal') is None and self.sucursal_id:
            extra['sucursal_id'] = self.sucursal_id
        socio = serializer.save(gym_id=gym_id, **extra)
        # Cada socio nuevo recibe su código de acceso automáticamente
        MetodoAcceso.objects.create(
            socio=socio,
            tipo='qr',
            token=f'R3B-QR-{socio.id:05d}-{random.randint(1000, 9999)}',
        )


class MembresiaViewSet(SucursalScopedMixin, viewsets.ModelViewSet):
    serializer_class = MembresiaSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return self.scope_sucursal(
            Membresia.objects.filter(socio__gym_id=self.request.user.gym_id)
        ).select_related('socio', 'plan')

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
        # Y además, recepción solo firma membresías en su propia sucursal.
        self.validar_escritura(serializer.validated_data.get('sucursal'))

    def perform_create(self, serializer):
        self._validar_pertenencia(serializer)
        serializer.save()

    def perform_update(self, serializer):
        self._validar_pertenencia(serializer)
        serializer.save()

    def get_throttles(self):
        # El ajuste verifica contraseñas: sin un límite propio se vuelve un banco de
        # pruebas de fuerza bruta contra las cuentas admin del gym.
        if self.action == 'ajustar_vencimiento':
            return [ScopedRateThrottle()]
        return super().get_throttles()

    throttle_scope = 'autorizacion'

    def _autorizador(self, password):
        """Devuelve el admin del gym cuya contraseña coincide, o None.

        Se prueba contra todos los admins del gym porque la UI solo pide la contraseña,
        sin decir de quién es. Se recorren todos aunque uno coincida antes: cortar en el
        primer acierto haría que el tiempo de respuesta delate qué cuenta acertó.
        """
        if not password:
            return None
        encontrado = None
        for admin in Usuario.objects.filter(
            gym_id=self.request.user.gym_id, rol__in=ROLES_ADMIN, is_active=True,
        ).order_by('id'):
            if admin.check_password(password) and encontrado is None:
                encontrado = admin
        return encontrado

    @action(detail=True, methods=['post'], url_path='ajustar-vencimiento')
    def ajustar_vencimiento(self, request, pk=None):
        """Mueve la fecha de próximo pago. Exige la contraseña de un admin del gym
        incluso si quien la pide ya es admin: la sesión abierta y desatendida en el
        mostrador es justamente el riesgo que esto cubre."""
        membresia = self.get_object()   # get_queryset ya acota al gym del usuario
        entrada = AjusteVencimientoInputSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        datos = entrada.validated_data

        autorizador = self._autorizador(datos['password'])
        if autorizador is None:
            raise PermissionDenied('Contraseña de autorización incorrecta.')

        nueva = datos['fecha_fin']
        if nueva < membresia.fecha_inicio:
            raise ValidationError(
                {'fecha_fin': 'La fecha de vencimiento no puede ser anterior al inicio '
                              f'de la membresía ({membresia.fecha_inicio}).'}
            )

        anterior_fecha = membresia.fecha_fin
        anterior_estado = membresia.estado

        # El estado sigue a la fecha, o el cambio no tiene efecto: `vigentes()` exige
        # estado='activa', así que extender una vencida sin reactivarla no abre la puerta.
        # 'suspendida' y 'pendiente_pago' son bloqueos deliberados y no se tocan aquí.
        nuevo_estado = anterior_estado
        hoy = timezone.localdate()
        if anterior_estado in ('activa', 'vencida'):
            nuevo_estado = 'activa' if nueva >= hoy else 'vencida'

        with transaction.atomic():
            membresia.fecha_fin = nueva
            membresia.estado = nuevo_estado
            membresia.save(update_fields=['fecha_fin', 'estado'])
            ajuste = AjusteMembresia.objects.create(
                membresia=membresia,
                fecha_anterior=anterior_fecha,
                fecha_nueva=nueva,
                estado_anterior=anterior_estado,
                estado_nuevo=nuevo_estado,
                motivo=datos.get('motivo', ''),
                solicitado_por=request.user,
                autorizado_por=autorizador,
            )

        return Response({
            'membresia': MembresiaSerializer(membresia).data,
            'ajuste': AjusteMembresiaSerializer(ajuste).data,
        }, status=status.HTTP_200_OK)

    @action(detail=True, methods=['get'])
    def ajustes(self, request, pk=None):
        """Bitácora de la membresía. Una auditoría que nadie puede leer no es auditoría."""
        membresia = self.get_object()
        return Response(AjusteMembresiaSerializer(
            membresia.ajustes.select_related('solicitado_por', 'autorizado_por'), many=True,
        ).data)


class PagoViewSet(SucursalScopedMixin, viewsets.ModelViewSet):
    serializer_class = PagoSerializer
    permission_classes = [permissions.IsAuthenticated]
    sucursal_lookup = 'membresia__sucursal'

    def get_queryset(self):
        return self.scope_sucursal(
            Pago.objects.filter(membresia__socio__gym_id=self.request.user.gym_id)
        )

    def perform_create(self, serializer):
        membresia = serializer.validated_data.get('membresia')
        if not membresia or membresia.socio.gym_id != self.request.user.gym_id:
            raise ValidationError({'membresia': 'Membresía no encontrada'})
        if self.sucursal_id is not None and membresia.sucursal_id != self.sucursal_id:
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


class GastoViewSet(SucursalScopedMixin, viewsets.ModelViewSet):
    serializer_class = GastoSerializer
    permission_classes = [permissions.IsAuthenticated, EsAdminGym]

    def get_queryset(self):
        qs = Gasto.objects.filter(gym_id=self.request.user.gym_id)
        objetivo = self.sucursal_id or self.sucursal_solicitada()
        if objetivo is None:
            return qs
        # Los gastos sin sucursal son del negocio entero (contador, publicidad) y
        # cuentan para cualquier local.
        return qs.filter(models.Q(sucursal_id=objetivo) | models.Q(sucursal__isnull=True))

    def perform_create(self, serializer):
        self.validar_escritura(serializer.validated_data.get('sucursal'))
        serializer.save(gym_id=self.request.user.gym_id, registrado_por=self.request.user)
