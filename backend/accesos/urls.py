from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    AccesoViewSet, MetodoAccesoViewSet, CheckInView, StatsView,
    SincronizarHuellaView, AsignarQRView, BuscarSocioView,
)

router = DefaultRouter()
router.register('metodos', MetodoAccesoViewSet, basename='metodos-acceso')
router.register('', AccesoViewSet, basename='accesos')

urlpatterns = [
    path('checkin/', CheckInView.as_view(), name='checkin'),
    path('stats/', StatsView.as_view(), name='accesos-stats'),
    path('sincronizar-huella/', SincronizarHuellaView.as_view(), name='sincronizar-huella'),
    path('asignar-qr/', AsignarQRView.as_view(), name='asignar-qr'),
    path('buscar-socio/', BuscarSocioView.as_view(), name='buscar-socio'),
    path('', include(router.urls)),
]
