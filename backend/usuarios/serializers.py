from django.contrib.auth.password_validation import validate_password as validar_password_django
from django.core.exceptions import ValidationError as ValidationErrorDjango
from django.utils import timezone
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from .models import Usuario
from .permissions import ROLES_ADMIN

DIAS_SEMANA = ['lunes', 'martes', 'miercoles', 'jueves', 'viernes', 'sabado', 'domingo']


class LoginSerializer(TokenObtainPairSerializer):
    """JWT con datos del usuario para que el frontend conozca su rol."""

    def validate(self, attrs):
        datos = super().validate(attrs)
        # `JWTUsuarioOperativo` corta a quien ya tiene token; esto corta a quien
        # intenta sacar uno nuevo. Sin las dos mitades, suspender a un cliente solo
        # le estorbaría hasta que volviera a iniciar sesión.
        gym = getattr(self.user, 'gym', None)
        if gym is not None and not gym.activo:
            raise serializers.ValidationError(
                'El gimnasio está suspendido. Contacta al proveedor del sistema.'
            )
        return datos

    @classmethod
    def get_token(cls, user):
        # Si el horario de hoy ya dice en qué sucursal trabaja, se asigna sola: no
        # tiene sentido preguntarle "¿en qué sucursal trabajas hoy?" a quien ya lo
        # dejó escrito en su horario. El día se recalcula en cada login (no se confía
        # en `user.sucursal` de una sesión vieja) para que quien rota de local entre
        # ayer y hoy no arrastre la sucursal de ayer.
        sucursal_hoy = None
        if user.sucursal_id or user.sucursales_permitidas.exists():
            dia_hoy = DIAS_SEMANA[timezone.localdate().weekday()]
            sucursal_hoy_id = (user.horario_semanal or {}).get(dia_hoy)
            if sucursal_hoy_id:
                sucursal_hoy = user.sucursales_permitidas.filter(id=sucursal_hoy_id).first()
                if sucursal_hoy and user.sucursal_id != sucursal_hoy.id:
                    user.sucursal = sucursal_hoy
                    user.save(update_fields=['sucursal'])

        token = super().get_token(user)
        token['nombre'] = user.nombre
        token['email'] = user.email
        token['rol'] = user.rol
        token['gym_id'] = user.gym_id
        # El frontend necesita saber si opera una sola sucursal para ocultar el
        # selector y rotular en qué caja está parado.
        token['sucursal_id'] = user.sucursal_id
        token['sucursal_nombre'] = user.sucursal.nombre if user.sucursal_id else None
        # Con qué sucursales puede rotar. El frontend ya no decide solo con esto si
        # pregunta al entrar: ver `requiere_seleccion_sucursal`.
        token['sucursales_permitidas'] = list(
            user.sucursales_permitidas.values('id', 'nombre')
        )
        # Solo se pregunta cuando puede rotar Y hoy no quedó resuelto por el horario.
        # Si el horario de hoy lo dejó fijado (arriba), o solo tiene una sucursal
        # permitida, entra derecho a su panel.
        token['requiere_seleccion_sucursal'] = (
            user.sucursales_permitidas.count() >= 2 and sucursal_hoy is None
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

    def validate_password(self, value):
        """Los validadores de `AUTH_PASSWORD_VALIDATORS` no se ejecutan solos.

        `set_password()` únicamente cifra: no comprueba nada. Sin esta llamada
        explícita la configuración de validadores existe pero no corre nunca, y "1"
        pasa como contraseña válida —verificado: alta 201 y login 200—.
        """
        try:
            validar_password_django(value)
        except ValidationErrorDjango as e:
            raise serializers.ValidationError(list(e.messages))
        return value

    def _validar_autoridad(self, attrs):
        """Quién puede otorgar qué.

        `rol` y `gym` viajaban como dos campos más de un `ModelSerializer`, y el
        permiso del ViewSet (`EsAdminGym`) solo mira si quien pide es admin, no qué
        está pidiendo. Como el admin de un gimnasio se encuentra dentro de su propio
        `get_queryset`, podía editarse a sí mismo: un PATCH con `rol=superadmin` le
        daba el panel del SaaS entero —y con él los demás clientes— en la siguiente
        petición, sin volver a iniciar sesión.
        """
        request = self.context.get('request')
        actor = getattr(request, 'user', None)
        if actor is None or not actor.is_authenticated:
            return attrs
        es_super = actor.rol == 'superadmin'

        # Tocar la ficha de un superadmin (su contraseña, por ejemplo) es tomar su
        # cuenta. Hoy el scoping por gym ya lo estorba porque el superadmin no tiene
        # gym, pero eso es un accidente de los datos, no una regla.
        if self.instance is not None and self.instance.rol == 'superadmin' and not es_super:
            raise serializers.ValidationError(
                {'detail': 'Solo un superadministrador puede editar esta cuenta.'}
            )

        rol = attrs.get('rol')
        if rol is not None:
            # Nadie se asciende a sí mismo. Un admin sí puede nombrar a otro admin:
            # lo que se cierra es el ascenso propio, que no necesita cómplice.
            if self.instance is not None and self.instance.pk == actor.pk and rol != self.instance.rol:
                raise serializers.ValidationError(
                    {'rol': 'No puedes cambiar tu propio rol. Pídeselo a otro administrador.'}
                )
            if rol == 'superadmin' and not es_super:
                raise serializers.ValidationError(
                    {'rol': 'El rol de superadministrador solo lo otorga otro superadministrador.'}
                )

        # `gym` no se elige: es el del actor al crear, y el que ya tenía al editar.
        # Escribible permitía a un admin mudarse al gimnasio de al lado con un PATCH
        # y leer sus datos con el mismo token, porque a partir de ahí el scoping por
        # gym trabaja a su favor.
        #
        # Se FIJA en vez de descartarse: la validación de sucursal de más abajo
        # compara contra `attrs['gym']` y se salta sola cuando el campo no viene, así
        # que un simple `pop` dejaría colar un empleado apuntando a la sucursal de
        # otro negocio —cambiar un agujero por otro—.
        if not es_super:
            attrs['gym'] = getattr(self.instance, 'gym', None) or actor.gym
        return attrs

    def validate(self, attrs):
        """La sucursal asignada tiene que ser del gym del usuario, y la activa
        y el horario tienen que salir del conjunto de permitidas.

        Sin esto se puede dejar a alguien apuntando a la sucursal de otro negocio, y
        el filtrado por sucursal lo mandaría a ver datos ajenos.
        """
        attrs = self._validar_autoridad(attrs)
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

        # Sin sucursal, el scoping (usuarios/scoping.py) no acota nada y el empleado
        # ve la caja, los socios y el inventario del negocio entero. Es el default
        # correcto para el dueño y una fuga para recepción, así que se exige.
        #
        # Solo se exige al crear o cuando la petición toca el rol o la sucursal: un
        # empleado antiguo que quedó sin sucursal debe poder seguir editándose (una
        # contraseña, una baja) en vez de quedar bloqueado por un hueco que no se
        # está tocando y que solo se puede cerrar guardando ese mismo formulario.
        rol = attrs.get('rol', getattr(self.instance, 'rol', None))
        toca_asignacion = 'rol' in attrs or 'sucursal' in attrs
        if (self.instance is None or toca_asignacion) and rol not in ROLES_ADMIN and sucursal is None:
            raise serializers.ValidationError(
                {'sucursal': 'Asigna la sucursal en la que trabaja: sin ella vería los '
                             'datos de todas las sucursales.'}
            )

        # Con sucursal asignada pero sin permitidas explícitas, se toma la suya como
        # la única. Deja el dato coherente: "dónde puede trabajar" nunca queda vacío
        # mientras "dónde trabaja ahora" tiene valor.
        if sucursal is not None and not permitidas_ids and 'sucursales_permitidas' not in attrs:
            attrs['sucursales_permitidas'] = [sucursal]
            # El horario se valida más abajo contra este conjunto: sin recalcularlo,
            # asignar un día a la sucursal recién tomada por defecto daría "sucursal
            # no permitida" contra la suya propia.
            permitidas_ids = {sucursal.id}

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
