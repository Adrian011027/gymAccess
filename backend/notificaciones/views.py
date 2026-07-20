from datetime import timedelta

from django.utils import timezone
from rest_framework import viewsets, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import Notificacion
from .serializers import NotificacionSerializer

RETENCION_DIAS = 15


class NotificacionViewSet(viewsets.ModelViewSet):
    serializer_class = NotificacionSerializer
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ['get', 'patch', 'post', 'head', 'options']

    def _limite_retencion(self):
        return timezone.now() - timedelta(days=RETENCION_DIAS)

    def get_queryset(self):
        gym_id = self.request.user.gym_id
        # Purga notificaciones más viejas que el período de retención
        Notificacion.objects.filter(gym_id=gym_id, creado_en__lt=self._limite_retencion()).delete()
        qs = Notificacion.objects.filter(gym_id=gym_id)
        if self.action == 'list':
            qs = qs.filter(archivada=False)
        return qs

    @action(detail=False, methods=['get'], url_path='historial')
    def historial(self, request):
        gym_id = request.user.gym_id
        Notificacion.objects.filter(gym_id=gym_id, creado_en__lt=self._limite_retencion()).delete()
        qs = Notificacion.objects.filter(gym_id=gym_id)
        return Response(NotificacionSerializer(qs, many=True).data)

    @action(detail=False, methods=['post'], url_path='marcar-todas-leidas')
    def marcar_todas_leidas(self, request):
        self.get_queryset().filter(leida=False).update(leida=True)
        return Response({'ok': True})

    @action(detail=False, methods=['post'], url_path='limpiar')
    def limpiar(self, request):
        """Oculta las notificaciones de la cortinita (se conservan para el historial)."""
        self.get_queryset().update(archivada=True, leida=True)
        return Response({'ok': True})
