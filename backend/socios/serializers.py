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
    edad = serializers.SerializerMethodField()
    es_menor = serializers.SerializerMethodField()
    consentimiento = serializers.SerializerMethodField()
    # No es campo del modelo: es la casilla que marca recepción en el alta. Se valida
    # en SocioViewSet.perform_create, que es donde se sabe si hay aviso publicado.
    acepta_aviso = serializers.BooleanField(write_only=True, required=False, default=False)

    class Meta:
        model = Socio
        fields = '__all__'
        extra_kwargs = {'gym': {'required': False}}
        read_only_fields = ['anonimizado_en', 'numero_socio']

    def get_validators(self):
        # `numero_socio` tiene un UniqueConstraint(gym, numero_socio) en el modelo.
        # DRF genera solo de eso un validador que exige "gym" en el body aunque el
        # campo esté marcado required=False —un efecto colateral conocido de
        # unique_together/UniqueConstraint en DRF, no una regla que se haya pedido—.
        # numero_socio nunca llega del cliente (SocioViewSet.perform_create lo asigna
        # siempre), así que ese validador no tiene nada que comprobar aquí: se filtra
        # para que el alta normal (sin "gym" en el body) siga funcionando.
        return [
            v for v in super().get_validators()
            if 'numero_socio' not in getattr(v, 'fields', ())
        ]

    def get_edad(self, obj):
        return obj.edad()

    def get_es_menor(self, obj):
        return obj.es_menor

    def get_consentimiento(self, obj):
        """Última evidencia de aceptación del aviso, o None si nunca aceptó.

        Va en el listado para que se vea de un vistazo a quién le falta: un socio
        sin consentimiento es un hueco que hay que cerrar, no un detalle.
        """
        c = obj.consentimientos.order_by('-aceptado_en').first()
        if not c:
            return None
        return {
            'version': c.documento.version,
            'aceptado_en': c.aceptado_en,
            'otorgado_por': c.otorgado_por,
        }

    def validate(self, attrs):
        """Un socio menor de edad necesita tutor identificado.

        Quien no puede consentir por sí mismo tampoco puede quedar registrado sin
        alguien que responda por él, así que el dato se exige en el alta y no
        "cuando se pueda".
        """
        instancia = self.instance
        nacimiento = attrs.get(
            'fecha_nacimiento', getattr(instancia, 'fecha_nacimiento', None),
        )
        if not nacimiento:
            return attrs

        from django.utils import timezone
        hoy = timezone.localdate()
        edad = hoy.year - nacimiento.year - (
            (hoy.month, hoy.day) < (nacimiento.month, nacimiento.day)
        )
        if nacimiento > hoy:
            raise serializers.ValidationError(
                {'fecha_nacimiento': 'La fecha de nacimiento no puede ser futura.'}
            )
        if edad >= 18:
            return attrs

        faltantes = {}
        for campo, etiqueta in (
            ('tutor_nombre', 'nombre del padre, madre o tutor'),
            ('tutor_telefono', 'teléfono del tutor'),
        ):
            valor = attrs.get(campo, getattr(instancia, campo, '') or '')
            if not str(valor).strip():
                faltantes[campo] = f'El socio es menor de edad: falta el {etiqueta}.'
        if faltantes:
            raise serializers.ValidationError(faltantes)
        return attrs

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
