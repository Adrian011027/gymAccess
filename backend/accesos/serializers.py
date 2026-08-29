from .enlaces import url_qr
from rest_framework import serializers
from .models import Acceso, MetodoAcceso


class MetodoAccesoSerializer(serializers.ModelSerializer):
    # La URL pública del PNG viaja junto al token para que el modal que acaba de
    # asignar el QR pueda mandarlo por chat sin recargar el listado de socios.
    imagen_url = serializers.SerializerMethodField()
    pagina_url = serializers.SerializerMethodField()

    class Meta:
        model = MetodoAcceso
        fields = '__all__'

    def get_imagen_url(self, obj):
        request = self.context.get('request')
        if obj.tipo != 'qr' or not obj.activo or request is None:
            return None
        return url_qr(request, obj.token, 'qr-imagen')

    def get_pagina_url(self, obj):
        request = self.context.get('request')
        if obj.tipo != 'qr' or not obj.activo or request is None:
            return None
        return url_qr(request, obj.token)


class AccesoSerializer(serializers.ModelSerializer):
    socio_nombre = serializers.CharField(source='socio.__str__', read_only=True)
    sucursal_nombre = serializers.CharField(source='sucursal.nombre', read_only=True)

    class Meta:
        model = Acceso
        fields = '__all__'
