from django.db import transaction
from rest_framework import serializers

from gyms.models import Gym, Sucursal
from socios.models import Membresia
from usuarios.models import Usuario

from .models import AccesoSoporte


class TenantSerializer(serializers.ModelSerializer):
    """Un gimnasio visto desde el negocio del SaaS, no desde dentro del gimnasio.

    Lo que importa aquí no es su horario ni su logo: es cuánto pesa como cliente
    —sucursales, socios, empleados— y si está al corriente.
    """

    # `source` apunta a las anotaciones `num_*` de TenantViewSet.get_queryset: no
    # pueden llamarse igual que el campo porque chocan con los `related_name` de Gym.
    sucursales = serializers.IntegerField(source='num_sucursales', read_only=True)
    empleados = serializers.IntegerField(source='num_empleados', read_only=True)
    socios = serializers.IntegerField(source='num_socios', read_only=True)
    socios_vigentes = serializers.SerializerMethodField()
    admin = serializers.SerializerMethodField()
    estado = serializers.SerializerMethodField()

    class Meta:
        model = Gym
        fields = [
            'id', 'nombre', 'tipo', 'telefono', 'email_contacto', 'direccion',
            'activo', 'creado_en', 'estado',
            'sucursales', 'empleados', 'socios', 'socios_vigentes', 'admin',
        ]
        read_only_fields = ['creado_en']

    def get_estado(self, obj):
        # Con un solo flag hoy solo hay dos estados. Cuando exista el modelo de
        # suscripción, 'prueba' y 'moroso' salen de ahí y este método es el punto
        # único donde se derivan: la UI no debería calcularlos por su cuenta.
        return 'activo' if obj.activo else 'suspendido'

    def get_socios_vigentes(self, obj):
        """Socios que hoy pueden entrar. Es la medida real de uso del sistema:
        un gimnasio con 300 socios de los que 40 están al corriente no consume
        como uno de 300."""
        # `socio__eliminado_en__isnull=True`: la membresia de un socio dado de baja
        # puede seguir siendo "vigente" por fecha y estado, asi que sin esto un socio
        # eliminado seguia contando como uso facturable del sistema.
        return (
            Membresia.objects.vigentes()
            .filter(
                socio__gym_id=obj.id, socio__eliminado_en__isnull=True,
                # La membresia de un dia de una visita esta vigente justo hoy: sin
                # esto, el uso facturable del gym sube y baja con los que pasaron.
                socio__es_visita=False,
            )
            .values('socio_id').distinct().count()
        )

    def get_admin(self, obj):
        u = (
            Usuario.objects.filter(gym_id=obj.id, rol='admin', is_active=True)
            .order_by('id').first()
        )
        return {'id': u.id, 'nombre': u.nombre, 'email': u.email} if u else None


class AltaTenantSerializer(serializers.Serializer):
    """Alta de un gimnasio nuevo en un solo paso.

    Un gym sin sucursal y sin admin no es un cliente, es una fila: nadie puede
    entrar a operarlo. Los tres objetos se crean juntos o no se crea ninguno, para
    que no queden tenants a medio nacer que haya que reparar a mano.
    """

    nombre = serializers.CharField(max_length=200)
    tipo = serializers.ChoiceField(choices=Gym.TIPO_CHOICES, default='mixto')
    telefono = serializers.CharField(max_length=20, required=False, allow_blank=True, default='')
    email_contacto = serializers.EmailField(required=False, allow_blank=True, default='')
    direccion = serializers.CharField(required=False, allow_blank=True, default='')

    sucursal_nombre = serializers.CharField(max_length=200, default='Matriz')
    sucursal_direccion = serializers.CharField(required=False, allow_blank=True, default='')

    admin_nombre = serializers.CharField(max_length=150)
    admin_email = serializers.EmailField()
    admin_password = serializers.CharField(write_only=True, min_length=8, trim_whitespace=False)

    def validate_admin_email(self, value):
        if Usuario.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError('Ya existe un usuario con ese correo.')
        return value

    @transaction.atomic
    def create(self, validated):
        gym = Gym.objects.create(
            nombre=validated['nombre'],
            tipo=validated['tipo'],
            telefono=validated['telefono'],
            email_contacto=validated['email_contacto'],
            direccion=validated['direccion'],
        )
        sucursal = Sucursal.objects.create(
            gym=gym,
            nombre=validated['sucursal_nombre'],
            direccion=validated['sucursal_direccion'],
        )
        admin = Usuario.objects.create_user(
            email=validated['admin_email'],
            password=validated['admin_password'],
            nombre=validated['admin_nombre'],
            rol='admin',
            gym=gym,
        )
        # El admin del gym no se ata a una sucursal: es el dueño y ve todo su negocio.
        # `sucursales_permitidas` vacío significa exactamente eso (usuarios/models.py).
        return {'gym': gym, 'sucursal': sucursal, 'admin': admin}


class AccesoSoporteSerializer(serializers.ModelSerializer):
    gym_nombre = serializers.CharField(source='gym.nombre', read_only=True)
    superadmin_nombre = serializers.CharField(source='superadmin.nombre', read_only=True)
    suplantado_nombre = serializers.CharField(source='suplantado.nombre', read_only=True)

    class Meta:
        model = AccesoSoporte
        fields = [
            'id', 'gym', 'gym_nombre', 'superadmin', 'superadmin_nombre',
            'suplantado', 'suplantado_nombre', 'motivo', 'ip', 'creado_en',
        ]
