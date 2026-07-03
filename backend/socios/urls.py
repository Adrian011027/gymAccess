from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import PlanViewSet, SocioViewSet, MembresiaViewSet, PagoViewSet, GastoViewSet

router = DefaultRouter()
router.register('planes', PlanViewSet, basename='planes')
router.register('gastos', GastoViewSet, basename='gastos')
router.register('membresias', MembresiaViewSet, basename='membresias')
router.register('pagos', PagoViewSet, basename='pagos')
router.register('', SocioViewSet, basename='socios')

urlpatterns = [path('', include(router.urls))]
