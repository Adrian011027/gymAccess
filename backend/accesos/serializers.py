from .enlaces import url_qr
from rest_framework import serializers
from gyms.models import Sucursal
from socios.models import Pago, Plan
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


class VisitaSerializer(serializers.Serializer):
    """Alta de un visitante de mostrador: quién es, qué plan paga y cómo.

    Solo acepta planes de tipo 'visita' del propio gym. Sin ese filtro, un POST con el
    id de la mensualidad daría acceso de un mes cobrando el precio de un día.
    """

    nombre = serializers.CharField(max_length=150)
    apellido = serializers.CharField(max_length=150, required=False, allow_blank=True)
    telefono = serializers.CharField(max_length=20, required=False, allow_blank=True)
    plan = serializers.IntegerField()
    sucursal = serializers.IntegerField()
    metodo = serializers.ChoiceField(choices=Pago.METODO_CHOICES)
    # Opcional: el precio sale del plan, pero el mostrador a veces cobra distinto
    # (cortesía, promoción). Si no viene, manda el plan.
    monto = serializers.DecimalField(
        max_digits=10, decimal_places=2, required=False, min_value=0,
    )

    def validate_plan(self, valor):
        gym_id = self.context['request'].user.gym_id
        plan = Plan.objects.filter(id=valor, gym_id=gym_id, tipo='visita').first()
        if plan is None:
            raise serializers.ValidationError(
                'Plan de visita no encontrado. Créalo en Configuración → Planes.'
            )
        return plan

    def validate_sucursal(self, valor):
        gym_id = self.context['request'].user.gym_id
        sucursal = Sucursal.objects.filter(id=valor, gym_id=gym_id).first()
        if sucursal is None:
            raise serializers.ValidationError('Sucursal no encontrada.')
        return sucursal

    def validate(self, attrs):
        if attrs.get('monto') is None:
            # `precio_en` y no `plan.precio` a secas: el gym que cobra la visita más
            # barata en una sucursal ya tiene esa excepción en `PrecioPlanSucursal`,
            # y el alta de membresías la respeta. Cobrando aquí el precio base, la
            # sucursal con descuento metía la diferencia de más en su corte cada día
            # y el precio que anuncia en la puerta dejaba de ser el que cobra.
            attrs['monto'] = attrs['plan'].precio_en(attrs['sucursal'].id)
        return attrs
