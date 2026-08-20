from rest_framework import serializers

from .models import AceptacionUsuario, ConsentimientoSocio, DocumentoLegal


class DocumentoLegalSerializer(serializers.ModelSerializer):
    tipo_display = serializers.CharField(source='get_tipo_display', read_only=True)
    publicado_por_nombre = serializers.CharField(source='publicado_por.nombre', read_only=True)

    class Meta:
        model = DocumentoLegal
        fields = [
            'id', 'gym', 'tipo', 'tipo_display', 'version', 'titulo', 'contenido',
            'vigente_desde', 'activo', 'creado_en',
            'publicado_por', 'publicado_por_nombre',
        ]
        read_only_fields = ['gym', 'creado_en', 'publicado_por']

    def validate_contenido(self, value):
        # Un aviso vacío se aceptaría igual y no probaría nada; mejor no dejar
        # publicar un documento sin texto que descubrirlo en una auditoría.
        if not value or not value.strip():
            raise serializers.ValidationError('El documento no puede estar vacío.')
        return value


class ConsentimientoSocioSerializer(serializers.ModelSerializer):
    socio_nombre = serializers.CharField(source='socio.__str__', read_only=True)
    documento_version = serializers.CharField(source='documento.version', read_only=True)
    documento_titulo = serializers.CharField(source='documento.titulo', read_only=True)
    capturado_por_nombre = serializers.CharField(source='capturado_por.nombre', read_only=True)

    class Meta:
        model = ConsentimientoSocio
        fields = [
            'id', 'socio', 'socio_nombre', 'documento', 'documento_version',
            'documento_titulo', 'otorgado_por', 'medio', 'tutor_nombre',
            'tutor_parentesco', 'aceptado_en', 'ip',
            'capturado_por', 'capturado_por_nombre',
        ]
        read_only_fields = fields


class AceptacionUsuarioSerializer(serializers.ModelSerializer):
    documento_titulo = serializers.CharField(source='documento.titulo', read_only=True)
    documento_version = serializers.CharField(source='documento.version', read_only=True)

    class Meta:
        model = AceptacionUsuario
        fields = [
            'id', 'usuario', 'documento', 'documento_titulo', 'documento_version',
            'aceptado_en', 'ip', 'user_agent',
        ]
        read_only_fields = fields
