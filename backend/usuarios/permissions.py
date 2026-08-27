from rest_framework.permissions import SAFE_METHODS, BasePermission

ROLES_ADMIN = ('admin', 'superadmin')


class EsAdminGym(BasePermission):
    """Solo el admin del gym (o superadmin) puede acceder."""

    def has_permission(self, request, view):
        return (
            request.user.is_authenticated
            and request.user.rol in ROLES_ADMIN
        )


class EsSuperAdmin(BasePermission):
    """Solo el dueño del SaaS. Es el único rol que opera *sobre* los gimnasios.

    Deliberadamente NO acepta 'admin': el admin es el dueño de un gimnasio, y darle
    entrada aquí le dejaría ver y tocar a los demás clientes del SaaS. `ROLES_ADMIN`
    mete a los dos en el mismo saco y por eso no se usa en este panel.
    """

    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.rol == 'superadmin'


class AdminOSoloLectura(BasePermission):
    """Cualquier usuario autenticado puede leer; solo admin puede escribir."""

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        return request.method in SAFE_METHODS or request.user.rol in ROLES_ADMIN
