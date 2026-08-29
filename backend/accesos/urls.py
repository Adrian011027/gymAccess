from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    AccesoViewSet, MetodoAccesoViewSet, CheckInView, StatsView,
    SincronizarHuellaView, AsignarQRView, BuscarSocioView, QRImagenView, QRPaginaView,
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
    # Pública: la abre el socio desde el chat, sin sesión. Va antes del router para
    # que no la capture la ruta de detalle de accesos.
    path('qr/<str:token>.png', QRImagenView.as_view(), name='qr-imagen'),
    # La que se manda por chat: página que muestra el QR. El .png de arriba es la
    # imagen que ella incrusta y la que WhatsApp usa para la miniatura.
    path('qr/<str:token>/', QRPaginaView.as_view(), name='qr-pagina'),
    path('', include(router.urls)),
]
