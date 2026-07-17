from rest_framework import serializers
from .models import Plan, Socio, Membresia, Pago, Gasto


class PlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = Plan
        fields = '__all__'


class SocioSerializer(serializers.ModelSerializer):
    membresia_activa = serializers.SerializerMethodField()
    codigo_acceso = serializers.SerializerMethodField()

    class Meta:
        model = Socio
        fields = '__all__'
        extra_kwargs = {'gym': {'required': False}}

    def get_codigo_acceso(self, obj):
        m = next((m for m in obj.metodos_acceso.all() if m.activo), None)
        return m.token if m else None

    def get_membresia_activa(self, obj):
        m = obj.membresias.filter(estado='activa').first()
        if not m:
            return None
        return {'id': m.id, 'plan': m.plan.nombre, 'fecha_fin': m.fecha_fin, 'estado': m.estado}


class MembresiaSerializer(serializers.ModelSerializer):
    socio_nombre = serializers.CharField(source='socio.__str__', read_only=True)
    plan_nombre = serializers.CharField(source='plan.nombre', read_only=True)

    class Meta:
        model = Membresia
        fields = '__all__'


class PagoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Pago
        fields = '__all__'
        read_only_fields = ['registrado_por', 'fecha']


class GastoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Gasto
        fields = '__all__'
        read_only_fields = ['registrado_por', 'gym']
