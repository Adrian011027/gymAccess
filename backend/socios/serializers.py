from rest_framework import serializers
from .models import AjusteMembresia, Plan, Socio, Membresia, Pago, Gasto


class PlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = Plan
        fields = '__all__'


class SocioSerializer(serializers.ModelSerializer):
    membresia_activa = serializers.SerializerMethodField()
    membresia_reciente = serializers.SerializerMethodField()
    codigo_acceso = serializers.SerializerMethodField()
    sucursal_nombre = serializers.CharField(source='sucursal.nombre', read_only=True)

    class Meta:
        model = Socio
        fields = '__all__'
        extra_kwargs = {'gym': {'required': False}}

    def get_codigo_acceso(self, obj):
        m = next((m for m in obj.metodos_acceso.all() if m.activo), None)
        return m.token if m else None

    def get_membresia_activa(self, obj):
        # Misma definición de "vigente" que usa el check-in (Membresia.objects.vigentes).
        # No basta con estado='activa': nada mueve el estado a 'vencida' cuando pasa
        # fecha_fin, así que hay que comparar fechas aquí también.
        m = obj.membresias.vigentes().first()
        if not m:
            return None
        return {'id': m.id, 'plan': m.plan.nombre, 'fecha_fin': m.fecha_fin, 'estado': m.estado}

    def get_membresia_reciente(self, obj):
        """La última membresía exista o no vigencia. `membresia_activa` es null para un
        socio vencido, que es justo a quien hay que ajustarle la fecha de próximo pago.
        """
        m = obj.membresias.order_by('-fecha_inicio', '-id').first()
        if not m:
            return None
        return {
            'id': m.id, 'plan': m.plan.nombre,
            'fecha_inicio': m.fecha_inicio, 'fecha_fin': m.fecha_fin, 'estado': m.estado,
        }


class MembresiaSerializer(serializers.ModelSerializer):
    socio_nombre = serializers.CharField(source='socio.__str__', read_only=True)
    plan_nombre = serializers.CharField(source='plan.nombre', read_only=True)
    plan_precio = serializers.DecimalField(source='plan.precio', read_only=True, max_digits=10, decimal_places=2)

    class Meta:
        model = Membresia
        fields = '__all__'


class PagoSerializer(serializers.ModelSerializer):
    socio_nombre = serializers.CharField(source='membresia.socio.__str__', read_only=True)
    plan_nombre = serializers.CharField(source='membresia.plan.nombre', read_only=True)
    registrado_por_nombre = serializers.CharField(source='registrado_por.nombre', read_only=True)

    class Meta:
        model = Pago
        fields = '__all__'
        read_only_fields = ['registrado_por', 'fecha']


class AjusteMembresiaSerializer(serializers.ModelSerializer):
    solicitado_por_nombre = serializers.CharField(source='solicitado_por.nombre', read_only=True)
    autorizado_por_nombre = serializers.CharField(source='autorizado_por.nombre', read_only=True)

    class Meta:
        model = AjusteMembresia
        fields = [
            'id', 'membresia', 'fecha_anterior', 'fecha_nueva',
            'estado_anterior', 'estado_nuevo', 'motivo',
            'solicitado_por', 'solicitado_por_nombre',
            'autorizado_por', 'autorizado_por_nombre', 'creado_en',
        ]


class AjusteVencimientoInputSerializer(serializers.Serializer):
    """La contraseña solo viaja en el body y nunca se persiste ni se devuelve."""

    fecha_fin = serializers.DateField()
    password = serializers.CharField(write_only=True, trim_whitespace=False)
    motivo = serializers.CharField(max_length=255, required=False, allow_blank=True, default='')


class GastoSerializer(serializers.ModelSerializer):
    sucursal_nombre = serializers.CharField(source='sucursal.nombre', read_only=True)

    class Meta:
        model = Gasto
        fields = '__all__'
        read_only_fields = ['registrado_por', 'gym']
