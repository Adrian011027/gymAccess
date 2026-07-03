from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import GymViewSet, SucursalViewSet, ClaseViewSet, EquipamientoViewSet

router = DefaultRouter()
router.register('sucursales', SucursalViewSet, basename='sucursales')
router.register('clases', ClaseViewSet, basename='clases')
router.register('equipamiento', EquipamientoViewSet, basename='equipamiento')
router.register('', GymViewSet, basename='gyms')

urlpatterns = [path('', include(router.urls))]
