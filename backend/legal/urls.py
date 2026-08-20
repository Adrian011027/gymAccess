from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    AceptarDocumentoView, ConsentimientoSocioViewSet, DocumentoLegalViewSet,
    PendientesAceptarView,
)

router = DefaultRouter()
router.register('consentimientos', ConsentimientoSocioViewSet, basename='consentimientos')
router.register('documentos', DocumentoLegalViewSet, basename='documentos-legales')

urlpatterns = [
    path('pendientes/', PendientesAceptarView.as_view(), name='legal-pendientes'),
    path('aceptar/', AceptarDocumentoView.as_view(), name='legal-aceptar'),
    path('', include(router.urls)),
]
