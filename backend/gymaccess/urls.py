from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from usuarios.views import LoginView, RefreshView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/auth/login/', LoginView.as_view(), name='token_obtain'),
    path('api/auth/refresh/', RefreshView.as_view(), name='token_refresh'),
    path('api/gyms/', include('gyms.urls')),
    path('api/socios/', include('socios.urls')),
    path('api/accesos/', include('accesos.urls')),
    path('api/usuarios/', include('usuarios.urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
