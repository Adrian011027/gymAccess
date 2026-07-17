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
        return token


class UsuarioSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=False)

    class Meta:
        model = Usuario
        fields = ['id', 'email', 'nombre', 'rol', 'gym', 'is_active', 'creado_en', 'password']
        read_only_fields = ['creado_en']

    def create(self, validated_data):
        password = validated_data.pop('password', None)
        user = Usuario(**validated_data)
        if password:
            user.set_password(password)
        user.save()
        return user

    def update(self, instance, validated_data):
        password = validated_data.pop('password', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if password:
            instance.set_password(password)
        instance.save()
        return instance
