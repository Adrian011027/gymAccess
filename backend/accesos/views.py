from django.db import models
from django.db.models import Count
from django.db.models.functions import ExtractHour
from django.utils import timezone
from rest_framework import viewsets, permissions, status
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.response import Response
from rest_framework.views import APIView
from .models import Acceso, MetodoAcceso
from .serializers import AccesoSerializer, MetodoAccesoSerializer
from socios.models import Membresia, Socio


class MetodoAccesoViewSet(viewsets.ModelViewSet):
    serializer_class = MetodoAccesoSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return MetodoAcceso.objects.filter(socio__gym_id=self.request.user.gym_id)


class SincronizarHuellaView(APIView):
    """Recibe el template ya capturado/matcheado por el agente local (SDK del lector)
    y lo asocia al socio como MetodoAcceso tipo huella."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        socio_id = request.data.get('socio_id')
        template = request.data.get('template')

        if not socio_id or not template:
            return Response({'error': 'socio_id y template son requeridos'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            socio = Socio.objects.get(id=socio_id, gym_id=request.user.gym_id)
        except Socio.DoesNotExist:
            return Response({'error': 'Socio no encontrado'}, status=status.HTTP_404_NOT_FOUND)

        if MetodoAcceso.objects.filter(token=template).exclude(socio=socio).exists():
            return Response({'error': 'Esta huella ya está registrada a otro socio'}, status=status.HTTP_409_CONFLICT)

        metodo, _ = MetodoAcceso.objects.update_or_create(
            socio=socio, tipo='huella',
            defaults={'token': template, 'activo': True},
        )
        return Response(MetodoAccesoSerializer(metodo).data, status=status.HTTP_200_OK)


class AccesoViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = AccesoSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Acceso.objects.filter(
            socio__gym_id=self.request.user.gym_id
        ).select_related('socio', 'sucursal').order_by('-timestamp')


class CheckInView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'checkin'

    def post(self, request):
        token = request.data.get('token')
        sucursal_id = request.data.get('sucursal_id')

        try:
            metodo = MetodoAcceso.objects.select_related('socio').get(
                token=token, activo=True, socio__gym_id=request.user.gym_id,
            )
        except MetodoAcceso.DoesNotExist:
            return Response({'error': 'Token inválido'}, status=status.HTTP_404_NOT_FOUND)

        socio = metodo.socio
        hoy = timezone.localdate()

        membresia = Membresia.objects.filter(
            socio=socio,
            estado='activa',
            fecha_inicio__lte=hoy,
        ).filter(
            models.Q(fecha_fin__gte=hoy) | models.Q(fecha_fin__isnull=True)
        ).first()

        if not membresia:
            Acceso.objects.create(
                socio=socio,
                sucursal_id=sucursal_id,
                metodo_usado=metodo.tipo,
                resultado='denegado',
                motivo_denegado='sin_membresia' if not Membresia.objects.filter(socio=socio).exists() else 'membresia_vencida',
            )
            return Response({
                'acceso': 'denegado',
                'socio': f'{socio.nombre} {socio.apellido}',
                'motivo': 'membresía no activa',
            }, status=status.HTTP_403_FORBIDDEN)

        Acceso.objects.create(
            socio=socio,
            sucursal_id=sucursal_id,
            membresia=membresia,
            metodo_usado=metodo.tipo,
            resultado='permitido',
        )
        return Response({
            'acceso': 'permitido',
            'socio': f'{socio.nombre} {socio.apellido}',
            'foto': request.build_absolute_uri(socio.foto.url) if socio.foto else None,
            'plan': membresia.plan.nombre,
            'vence': membresia.fecha_fin,
        })


class StatsView(APIView):
    """Dashboard analytics: horarios concurridos + totales del gym."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        gym_id = request.user.gym_id
        hoy = timezone.localdate()
        inicio_mes = hoy.replace(day=1)

        accesos_qs = Acceso.objects.filter(
            socio__gym_id=gym_id,
            resultado='permitido',
        )

        por_hora = (
            accesos_qs
            .annotate(hora=ExtractHour('timestamp'))
            .values('hora')
            .annotate(total=Count('id'))
            .order_by('hora')
        )

        accesos_hoy = accesos_qs.filter(timestamp__date=hoy).count()
        accesos_mes = accesos_qs.filter(timestamp__date__gte=inicio_mes).count()

        return Response({
            'horarios_concurridos': list(por_hora),
            'accesos_hoy': accesos_hoy,
            'accesos_mes': accesos_mes,
        })
