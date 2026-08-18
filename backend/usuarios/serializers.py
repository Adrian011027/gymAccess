from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from .models import Usuario


class LoginSerializer(TokenObtainPairSerializer):
    """JWT con datos del usuario para que el frontend conozca su rol."""

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['nombre'] = user.nombre
        token['email'] = user.email
        token['rol'] = user.rol
        token['gym_id'] = user.gym_id
        # El frontend necesita saber si opera una sola sucursal para ocultar el
        # selector y rotular en qué caja está parado.
        token['sucursal_id'] = user.sucursal_id
        token['sucursal_nombre'] = user.sucursal.nombre if user.sucursal_id else None
        # Con qué sucursales puede rotar: si son 2+, el frontend pide elegir una
        # al entrar antes de mandarlo al panel.
        token['sucursales_permitidas'] = list(
            user.sucursales_permitidas.values('id', 'nombre')
        )
        return token


class UsuarioSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=False)
    sucursal_nombre = serializers.CharField(source='sucursal.nombre', read_only=True)

    class Meta:
        model = Usuario
        fields = [
            'id', 'email', 'nombre', 'rol', 'gym', 'sucursal', 'sucursal_nombre',
            'sucursales_permitidas', 'horario_semanal',
            'is_active', 'creado_en', 'password',
        ]
        read_only_fields = ['creado_en']

    def validate(self, attrs):
        """La sucursal asignada tiene que ser del gym del usuario, y la activa
        y el horario tienen que salir del conjunto de permitidas.

        Sin esto se puede dejar a alguien apuntando a la sucursal de otro negocio, y
        el filtrado por sucursal lo mandaría a ver datos ajenos.
        """
        sucursal = attrs.get('sucursal', getattr(self.instance, 'sucursal', None))
        gym = attrs.get('gym', getattr(self.instance, 'gym', None))
        if sucursal is not None and gym is not None and sucursal.gym_id != gym.id:
            raise serializers.ValidationError(
                {'sucursal': 'La sucursal no pertenece al gym del usuario.'}
            )

        permitidas = attrs.get(
            'sucursales_permitidas',
            list(self.instance.sucursales_permitidas.all()) if self.instance else [],
        )
        permitidas_ids = {s.id for s in permitidas}
        if sucursal is not None and permitidas_ids and sucursal.id not in permitidas_ids:
            raise serializers.ValidationError(
                {'sucursal': 'La sucursal activa debe ser una de las permitidas.'}
            )

        horario = attrs.get('horario_semanal')
        if horario:
            dias_validos = {
                'lunes', 'martes', 'miercoles', 'jueves', 'viernes', 'sabado', 'domingo',
            }
            horario_normalizado = {}
            for dia, valor in horario.items():
                if dia not in dias_validos:
                    raise serializers.ValidationError(
                        {'horario_semanal': f'Día inválido: {dia}.'}
                    )
                # El frontend manda el id de sucursal como string (viene de un <select>).
                valor_id = None
                if valor not in (None, ''):
                    try:
                        valor_id = int(valor)
                    except (TypeError, ValueError):
                        raise serializers.ValidationError(
                            {'horario_semanal': f'Sucursal inválida en {dia}.'}
                        )
                if valor_id is not None and valor_id not in permitidas_ids:
                    raise serializers.ValidationError(
                        {'horario_semanal': f'La sucursal de {dia} debe ser una de las permitidas.'}
                    )
                horario_normalizado[dia] = valor_id
            attrs['horario_semanal'] = horario_normalizado
        return attrs

    def create(self, validated_data):
        password = validated_data.pop('password', None)
        permitidas = validated_data.pop('sucursales_permitidas', None)
        user = Usuario(**validated_data)
        if password:
            user.set_password(password)
        user.save()
        if permitidas is not None:
            user.sucursales_permitidas.set(permitidas)
        return user

    def update(self, instance, validated_data):
        password = validated_data.pop('password', None)
        permitidas = validated_data.pop('sucursales_permitidas', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if password:
            instance.set_password(password)
        instance.save()
        if permitidas is not None:
            instance.sucursales_permitidas.set(permitidas)
        return instance
