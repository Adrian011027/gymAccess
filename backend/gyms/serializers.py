from datetime import datetime

from rest_framework import serializers
from .models import Gym, Sucursal, Clase, Equipamiento

DIAS_HORARIO = ['lun', 'mar', 'mie', 'jue', 'vie', 'sab', 'dom']


def _hora(valor, campo):
    """Convierte 'HH:MM' a time; el JSONField acepta cualquier cosa si no se valida."""
    if not isinstance(valor, str):
        raise serializers.ValidationError({'horario': f'{campo}: se esperaba HH:MM.'})
    try:
        return datetime.strptime(valor[:5], '%H:%M').time()
    except ValueError:
        raise serializers.ValidationError({'horario': f'{campo}: hora inválida "{valor}".'})


class SucursalSerializer(serializers.ModelSerializer):
    class Meta:
        model = Sucursal
        fields = '__all__'


class GymSerializer(serializers.ModelSerializer):
    sucursales = SucursalSerializer(many=True, read_only=True)

    class Meta:
        model = Gym
        fields = '__all__'
        # `activo` es la palanca de cobranza del SaaS (suspender / reactivar un
        # cliente), no una preferencia del gimnasio: se cambia desde
        # `/api/saas/tenants/<id>/suspender/` y en ningún otro sitio.
        read_only_fields = ['activo']

    def validate_horario(self, value):
        """Valida el horario semanal y sus descansos.

        Un JSONField guarda lo que sea, así que sin esto un descanso al revés
        (15:00-13:00) o fuera del turno se persiste y luego la pantalla muestra
        un horario imposible sin que nadie sepa de dónde salió.
        """
        if value in (None, ''):
            return {}
        if not isinstance(value, dict):
            raise serializers.ValidationError('Se esperaba un objeto por día.')

        limpio = {}
        for dia, cfg in value.items():
            if dia not in DIAS_HORARIO:
                raise serializers.ValidationError(f'Día inválido: {dia}.')
            if not isinstance(cfg, dict):
                raise serializers.ValidationError(f'{dia}: se esperaba un objeto.')

            abierto = bool(cfg.get('abierto', True))
            if not abierto:
                limpio[dia] = {'abierto': False}
                continue

            inicio = _hora(cfg.get('inicio'), f'{dia}.inicio')
            fin = _hora(cfg.get('fin'), f'{dia}.fin')
            if inicio >= fin:
                raise serializers.ValidationError(
                    f'{dia}: la apertura debe ser anterior al cierre.'
                )

            descansos = cfg.get('descansos') or []
            if not isinstance(descansos, list):
                raise serializers.ValidationError(f'{dia}: descansos debe ser una lista.')

            normalizados = []
            for i, d in enumerate(descansos, 1):
                if not isinstance(d, dict):
                    raise serializers.ValidationError(f'{dia}: descanso {i} inválido.')
                di = _hora(d.get('inicio'), f'{dia}.descanso{i}.inicio')
                df = _hora(d.get('fin'), f'{dia}.descanso{i}.fin')
                if di >= df:
                    raise serializers.ValidationError(
                        f'{dia}: el descanso {i} termina antes de empezar.'
                    )
                if di < inicio or df > fin:
                    raise serializers.ValidationError(
                        f'{dia}: el descanso {i} cae fuera del horario de atención.'
                    )
                normalizados.append({'inicio': di.strftime('%H:%M'), 'fin': df.strftime('%H:%M')})

            normalizados.sort(key=lambda d: d['inicio'])
            for a, b in zip(normalizados, normalizados[1:]):
                if b['inicio'] < a['fin']:
                    raise serializers.ValidationError(f'{dia}: los descansos se enciman.')

            limpio[dia] = {
                'abierto': True,
                'inicio': inicio.strftime('%H:%M'),
                'fin': fin.strftime('%H:%M'),
                'descansos': normalizados,
            }
        return limpio


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
