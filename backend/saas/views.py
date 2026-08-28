"""Panel del SaaS: el centro de operaciones del dueño del producto.

Los ViewSets del resto del proyecto acotan por `request.user.gym_id` — miran *dentro*
de un gimnasio. Estos miran *a través* de todos, y por eso viven aparte en vez de
colgarse de los existentes con un `if rol == 'superadmin'`: mezclar los dos alcances
en la misma vista es como se filtran datos de un cliente a otro.
"""

from django.db.models import Count, Q
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from gyms.models import Gym, Sucursal
from socios.models import Membresia, Socio
from usuarios.models import Usuario
from usuarios.permissions import EsSuperAdmin
from usuarios.serializers import LoginSerializer

from .models import AccesoSoporte
from .serializers import (
    AccesoSoporteSerializer, AltaTenantSerializer, TenantSerializer,
)


def ip_de(request):
    """IP del cliente respetando el proxy. Copiada de `legal.views` a propósito:
    importar desde allá acoplaría el panel del SaaS al módulo legal por una utilidad
    de tres líneas."""
    reenviada = request.META.get('HTTP_X_FORWARDED_FOR')
    if reenviada:
        return reenviada.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


class TenantViewSet(viewsets.ModelViewSet):
    """Los gimnasios como clientes del SaaS."""

    serializer_class = TenantSerializer
    permission_classes = [IsAuthenticated, EsSuperAdmin]

    def get_queryset(self):
        # Sin filtro por `activo`: un cliente suspendido sigue siendo un cliente y
        # tiene que verse en la lista. `GymViewSet` sí lo filtra, porque allá un gym
        # inactivo es uno que no debe operar.
        # Prefijo `num_`: `sucursales`, `socios` y `usuarios` ya son `related_name` en
        # Gym, y Django rechaza una anotación que se llame como un campo del modelo.
        return Gym.objects.annotate(
            num_sucursales=Count('sucursales', filter=Q(sucursales__activa=True), distinct=True),
            num_empleados=Count('usuarios', filter=Q(usuarios__is_active=True), distinct=True),
            # `eliminado_en` ademas de `activo`: la baja logica ya apaga `activo`,
            # pero depender de eso deja el conteo a merced de un PATCH que lo
            # reactive sin restaurar al socio.
            num_socios=Count(
                'socios',
                filter=Q(socios__activo=True, socios__eliminado_en__isnull=True),
                distinct=True,
            ),
        ).order_by('-creado_en')

    def create(self, request, *args, **kwargs):
        """Alta completa: gym + primera sucursal + usuario admin, en una transacción."""
        entrada = AltaTenantSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        creado = entrada.save()
        gym = self.get_queryset().get(id=creado['gym'].id)
        return Response(
            {
                'gym': TenantSerializer(gym).data,
                'sucursal': {'id': creado['sucursal'].id, 'nombre': creado['sucursal'].nombre},
                'admin': {'id': creado['admin'].id, 'email': creado['admin'].email},
            },
            status=status.HTTP_201_CREATED,
        )

    def destroy(self, request, *args, **kwargs):
        """No se borra un tenant: se suspende.

        De un gym cuelgan socios, pagos y bitácora de accesos. Un DELETE los arrastra
        por cascada y con ellos la contabilidad que el CFF obliga a conservar cinco
        años — el mismo criterio que ya se aplica a socios y empleados.
        """
        raise ValidationError({
            'gym': 'Un gimnasio no se elimina: suspéndelo con POST /suspender/. '
                   'Borrarlo arrastraría sus pagos y su bitácora de accesos.',
        })

    @action(detail=True, methods=['post'])
    def suspender(self, request, pk=None):
        """Corta el acceso del gimnasio sin tocar sus datos.

        `Gym.activo = False` lo saca de `GymViewSet.get_queryset`, que filtra por
        `activo=True`: sus usuarios dejan de poder operarlo, pero todo sigue ahí
        para cuando se ponga al corriente.
        """
        gym = self.get_object()
        if not gym.activo:
            raise ValidationError({'gym': 'Este gimnasio ya está suspendido.'})
        gym.activo = False
        gym.save(update_fields=['activo'])
        return Response(TenantSerializer(self.get_queryset().get(id=gym.id)).data)

    @action(detail=True, methods=['post'])
    def reactivar(self, request, pk=None):
        gym = self.get_object()
        if gym.activo:
            raise ValidationError({'gym': 'Este gimnasio ya está activo.'})
        gym.activo = True
        gym.save(update_fields=['activo'])
        return Response(TenantSerializer(self.get_queryset().get(id=gym.id)).data)

    @action(detail=True, methods=['post'])
    def impersonar(self, request, pk=None):
        """Devuelve un JWT del admin del gimnasio, para dar soporte sin pedirle la
        contraseña al cliente.

        Se exige un motivo y queda en `AccesoSoporte`: ver los datos personales de
        socios ajenos no puede ser una operación silenciosa. El token lleva además
        las marcas `soporte` y `soporte_de`, para que el rastro viaje en el propio
        token y no solo en la base.
        """
        gym = self.get_object()
        motivo = str(request.data.get('motivo', '')).strip()
        if not motivo:
            raise ValidationError({'motivo': 'Indica para qué necesitas entrar.'})

        destino = (
            Usuario.objects.filter(gym_id=gym.id, rol='admin', is_active=True)
            .order_by('id').first()
        )
        if destino is None:
            raise ValidationError({
                'gym': 'Este gimnasio no tiene un admin activo al que suplantar.',
            })

        AccesoSoporte.objects.create(
            gym=gym, superadmin=request.user, suplantado=destino,
            motivo=motivo, ip=ip_de(request),
        )

        token = LoginSerializer.get_token(destino)
        token['soporte'] = True
        token['soporte_de'] = request.user.id
        return Response({
            'access': str(token.access_token),
            'refresh': str(token),
            'suplantado': {'id': destino.id, 'nombre': destino.nombre, 'email': destino.email},
            'gym': {'id': gym.id, 'nombre': gym.nombre},
        })

    @action(detail=True, methods=['get'], url_path='accesos-soporte')
    def accesos_soporte(self, request, pk=None):
        gym = self.get_object()
        return Response(AccesoSoporteSerializer(
            gym.accesos_soporte.select_related('superadmin', 'suplantado', 'gym'), many=True,
        ).data)


class SoporteView(APIView):
    """Toda la bitácora de soporte, de todos los clientes.

    La que cuelga de un tenant sirve para responderle a *ese* cliente; esta sirve para
    mirarse a uno mismo: cuántas veces se entró a cuentas ajenas este mes y con qué
    motivo. Un registro que solo se consulta cuando alguien reclama no vigila nada.
    """

    permission_classes = [IsAuthenticated, EsSuperAdmin]

    def get(self, request):
        qs = AccesoSoporte.objects.select_related('gym', 'superadmin', 'suplantado')
        return Response(AccesoSoporteSerializer(qs[:200], many=True).data)


class ResumenView(APIView):
    """Los números del negocio del SaaS, no los de ningún gimnasio."""

    permission_classes = [IsAuthenticated, EsSuperAdmin]

    def get(self, request):
        gyms = Gym.objects.all()
        socios_vigentes = (
            Membresia.objects.vigentes()
            .filter(socio__eliminado_en__isnull=True)
            .values('socio_id').distinct().count()
        )
        return Response({
            'gyms_total': gyms.count(),
            'gyms_activos': gyms.filter(activo=True).count(),
            'gyms_suspendidos': gyms.filter(activo=False).count(),
            'sucursales': Sucursal.objects.filter(activa=True).count(),
            'empleados': Usuario.objects.filter(is_active=True, gym__isnull=False).count(),
            'socios': Socio.objects.vivos().filter(activo=True).count(),
            # Socios que hoy pueden entrar. Es la medida de uso real del producto y
            # la que sostiene el argumento de subir de paquete.
            'socios_vigentes': socios_vigentes,
        })
