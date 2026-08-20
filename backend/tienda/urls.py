from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import ProductoViewSet, VentaViewSet

router = DefaultRouter()
router.register('productos', ProductoViewSet, basename='productos')
router.register('ventas', VentaViewSet, basename='ventas')

urlpatterns = [path('', include(router.urls))]
