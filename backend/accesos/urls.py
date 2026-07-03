from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import AccesoViewSet, MetodoAccesoViewSet, CheckInView, StatsView

router = DefaultRouter()
router.register('metodos', MetodoAccesoViewSet, basename='metodos-acceso')
router.register('', AccesoViewSet, basename='accesos')

urlpatterns = [
    path('checkin/', CheckInView.as_view(), name='checkin'),
    path('stats/', StatsView.as_view(), name='accesos-stats'),
    path('', include(router.urls)),
]
