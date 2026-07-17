from rest_framework.permissions import SAFE_METHODS, BasePermission

ROLES_ADMIN = ('admin', 'superadmin')


class EsAdminGym(BasePermission):
    """Solo el admin del gym (o superadmin) puede acceder."""

    def has_permission(self, request, view):
        return (
            request.user.is_authenticated
            and request.user.rol in ROLES_ADMIN
        )


class AdminOSoloLectura(BasePermission):
    """Cualquier usuario autenticado puede leer; solo admin puede escribir."""

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        return request.method in SAFE_METHODS or request.user.rol in ROLES_ADMIN
