"""
Mixins de control de acceso basado en roles (RF-04: "El sistema debe
restringir el acceso a las funcionalidades y a la información según el rol
asignado al usuario").

Se implementan como mixins de Class-Based Views para reforzar el diseño
orientado a objetos del sistema (herencia y reutilización de comportamiento
entre las vistas de todos los módulos).
"""

from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import PermissionDenied

from .constants import ROL_ADMIN


class RolRequeridoMixin(LoginRequiredMixin, UserPassesTestMixin):
    """
    Restringe el acceso a una vista a una lista de roles determinada.
    Uso:

        class ObraCreateView(RolRequeridoMixin, CreateView):
            roles_permitidos = [ROL_ADMIN, ROL_APOYO]
            ...

    El administrador del sistema (ROL_ADMIN) siempre tiene acceso, salvo que
    se indique explícitamente `permitir_admin = False`.
    """

    roles_permitidos: list[str] = []
    permitir_admin = True
    raise_exception = False

    def test_func(self):
        usuario = self.request.user
        if not usuario.is_authenticated:
            return False
        if self.permitir_admin and usuario.rol == ROL_ADMIN:
            return True
        return usuario.rol in self.roles_permitidos

    def handle_no_permission(self):
        if self.request.user.is_authenticated:
            raise PermissionDenied(
                "No cuenta con permisos suficientes para acceder a este módulo."
            )
        return super().handle_no_permission()
