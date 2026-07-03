from rest_framework import serializers
from .models import Acceso, MetodoAcceso


class MetodoAccesoSerializer(serializers.ModelSerializer):
    class Meta:
        model = MetodoAcceso
        fields = '__all__'


class AccesoSerializer(serializers.ModelSerializer):
    socio_nombre = serializers.CharField(source='socio.__str__', read_only=True)
    sucursal_nombre = serializers.CharField(source='sucursal.nombre', read_only=True)

    class Meta:
        model = Acceso
        fields = '__all__'
