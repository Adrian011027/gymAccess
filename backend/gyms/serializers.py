from rest_framework import serializers
from .models import Gym, Sucursal, Clase, Equipamiento


class SucursalSerializer(serializers.ModelSerializer):
    class Meta:
        model = Sucursal
        fields = '__all__'


class GymSerializer(serializers.ModelSerializer):
    sucursales = SucursalSerializer(many=True, read_only=True)

    class Meta:
        model = Gym
        fields = '__all__'


class ClaseSerializer(serializers.ModelSerializer):
    tipo_display = serializers.CharField(source='get_tipo_display', read_only=True)
    nivel_display = serializers.CharField(source='get_nivel_display', read_only=True)

    class Meta:
        model = Clase
        fields = '__all__'
        read_only_fields = ['gym']


class EquipamientoSerializer(serializers.ModelSerializer):
    categoria_display = serializers.CharField(source='get_categoria_display', read_only=True)

    class Meta:
        model = Equipamiento
        fields = '__all__'
        read_only_fields = ['gym']
