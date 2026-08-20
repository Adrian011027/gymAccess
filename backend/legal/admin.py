from django.contrib import admin

from .models import AceptacionUsuario, ConsentimientoSocio, DocumentoLegal


@admin.register(DocumentoLegal)
class DocumentoLegalAdmin(admin.ModelAdmin):
    list_display = ['tipo', 'version', 'gym', 'vigente_desde', 'activo']
    list_filter = ['tipo', 'activo']


@admin.register(ConsentimientoSocio)
class ConsentimientoSocioAdmin(admin.ModelAdmin):
    list_display = ['socio', 'documento', 'otorgado_por', 'aceptado_en']
    list_filter = ['otorgado_por', 'medio']
    # Es evidencia: se consulta, no se edita.
    readonly_fields = [f.name for f in ConsentimientoSocio._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(AceptacionUsuario)
class AceptacionUsuarioAdmin(admin.ModelAdmin):
    list_display = ['usuario', 'documento', 'aceptado_en', 'ip']
    readonly_fields = [f.name for f in AceptacionUsuario._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
