import os

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from usuarios.views import LoginView, RefreshView

# El panel de Django no pasa por el throttling de DRF —esos límites solo aplican a
# vistas DRF—, así que su formulario de login es la superficie de fuerza bruta menos
# protegida del sistema y los bots escanean /admin/ sin parar. En producción se
# exporta DJANGO_ADMIN_URL con algo no adivinable; vacío lo apaga del todo.
_admin_url = os.environ.get('DJANGO_ADMIN_URL', 'admin/')

urlpatterns = [
    path('api/auth/login/', LoginView.as_view(), name='token_obtain'),
    path('api/auth/refresh/', RefreshView.as_view(), name='token_refresh'),
    path('api/gyms/', include('gyms.urls')),
    path('api/socios/', include('socios.urls')),
    path('api/accesos/', include('accesos.urls')),
    path('api/usuarios/', include('usuarios.urls')),
    path('api/notificaciones/', include('notificaciones.urls')),
    path('api/tienda/', include('tienda.urls')),
    path('api/legal/', include('legal.urls')),
    path('api/saas/', include('saas.urls')),
]

if _admin_url:
    urlpatterns.insert(0, path(_admin_url, admin.site.urls))

# En produccion nginx sirve /media/; `static()` no hace nada con DEBUG=False.
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
