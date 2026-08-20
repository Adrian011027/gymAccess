from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from usuarios.permissions import AdminOSoloLectura

from .models import AceptacionUsuario, ConsentimientoSocio, DocumentoLegal
from .serializers import (
    AceptacionUsuarioSerializer, ConsentimientoSocioSerializer, DocumentoLegalSerializer,
)


def ip_de(request):
    """IP del cliente respetando el proxy inverso de producción.

    Detrás de nginx/Cloudflare, REMOTE_ADDR es siempre el del proxy: sin leer
    X-Forwarded-For toda la evidencia quedaría registrada con la misma IP.
    """
    reenviada = request.META.get('HTTP_X_FORWARDED_FOR', '')
    if reenviada:
        return reenviada.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


# Documentos que el propio gym redacta; los del proveedor (términos y convenio) se
# publican sin gym y el gym solo los lee.
TIPOS_DEL_GYM = (DocumentoLegal.AVISO_PRIVACIDAD,)


class DocumentoLegalViewSet(viewsets.ModelViewSet):
    """Documentos que aplican a este gym: los suyos más los del proveedor."""

    serializer_class = DocumentoLegalSerializer
    permission_classes = [permissions.IsAuthenticated, AdminOSoloLectura]

    def get_queryset(self):
        from django.db.models import Q
        return DocumentoLegal.objects.filter(
            Q(gym_id=self.request.user.gym_id) | Q(gym__isnull=True)
        )

    def perform_create(self, serializer):
        tipo = serializer.validated_data.get('tipo')
        if tipo not in TIPOS_DEL_GYM:
            # Los términos del servicio y el convenio de encargado los redacta el
            # proveedor: si cada gym pudiera reescribirlos, dejarían de respaldarlo.
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied(
                'Este documento lo publica el proveedor del software, no el gym.'
            )
        serializer.save(gym_id=self.request.user.gym_id, publicado_por=self.request.user)

    def perform_update(self, serializer):
        from rest_framework.exceptions import PermissionDenied
        if serializer.instance.gym_id is None:
            raise PermissionDenied('Este documento lo mantiene el proveedor del software.')
        # Editar el texto de una versión ya aceptada rompería la evidencia: quien la
        # firmó habría aceptado otra cosa. Se publica una versión nueva.
        if serializer.instance.consentimientos.exists() or serializer.instance.aceptaciones.exists():
            campos = set(serializer.validated_data) - {'activo', 'vigente_desde'}
            if campos:
                raise PermissionDenied(
                    'Esta versión ya fue aceptada por alguien: publica una versión '
                    'nueva en lugar de modificar el texto.'
                )
        serializer.save()

    @action(detail=False, methods=['get'])
    def vigentes(self, request):
        """El documento que hoy debe mostrarse, por tipo."""
        gym_id = request.user.gym_id
        salida = {}
        for tipo, _ in DocumentoLegal.TIPO_CHOICES:
            doc = DocumentoLegal.vigente(tipo, gym_id if tipo in TIPOS_DEL_GYM else None)
            salida[tipo] = DocumentoLegalSerializer(doc).data if doc else None
        return Response(salida)


class PendientesAceptarView(APIView):
    """Documentos del proveedor que este usuario todavía no acepta.

    El frontend bloquea la aplicación mientras la lista no esté vacía: aceptar
    después de haber usado el sistema no acredita gran cosa.
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        ya = set(
            AceptacionUsuario.objects
            .filter(usuario=request.user).values_list('documento_id', flat=True)
        )
        pendientes = []
        for tipo in (DocumentoLegal.TERMINOS_SERVICIO, DocumentoLegal.CONVENIO_ENCARGADO):
            doc = DocumentoLegal.vigente(tipo, None)
            # El convenio de encargado lo pacta el dueño del negocio, no recepción.
            if not doc or doc.id in ya:
                continue
            if tipo == DocumentoLegal.CONVENIO_ENCARGADO and request.user.rol not in ('admin', 'superadmin'):
                continue
            pendientes.append(doc)
        return Response(DocumentoLegalSerializer(pendientes, many=True).data)


class AceptarDocumentoView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        documento_id = request.data.get('documento')
        try:
            doc = DocumentoLegal.objects.get(id=documento_id, gym__isnull=True, activo=True)
        except (DocumentoLegal.DoesNotExist, ValueError, TypeError):
            return Response(
                {'documento': 'Documento no encontrado.'}, status=status.HTTP_404_NOT_FOUND,
            )
        aceptacion, creada = AceptacionUsuario.objects.get_or_create(
            usuario=request.user, documento=doc,
            defaults={
                'ip': ip_de(request),
                'user_agent': request.META.get('HTTP_USER_AGENT', '')[:300],
            },
        )
        return Response(
            AceptacionUsuarioSerializer(aceptacion).data,
            status=status.HTTP_201_CREATED if creada else status.HTTP_200_OK,
        )


class ConsentimientoSocioViewSet(viewsets.ReadOnlyModelViewSet):
    """Solo lectura: el consentimiento se registra al dar de alta al socio.

    Permitir crearlo o editarlo suelto haría trivial fabricar evidencia después
    de los hechos, que es justo lo contrario de para lo que sirve.
    """

    serializer_class = ConsentimientoSocioSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = ConsentimientoSocio.objects.filter(
            socio__gym_id=self.request.user.gym_id
        ).select_related('socio', 'documento', 'capturado_por')
        socio = self.request.query_params.get('socio')
        return qs.filter(socio_id=socio) if socio else qs
