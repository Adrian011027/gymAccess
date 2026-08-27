from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import ResumenView, SoporteView, TenantViewSet

router = DefaultRouter()
router.register('tenants', TenantViewSet, basename='tenants')

urlpatterns = [
    path('resumen/', ResumenView.as_view(), name='saas-resumen'),
    path('soporte/', SoporteView.as_view(), name='saas-soporte'),
    path('', include(router.urls)),
]
