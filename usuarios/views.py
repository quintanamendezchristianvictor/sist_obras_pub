from django.contrib import messages
from django.contrib.auth import views as auth_views
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views.generic import CreateView, ListView, UpdateView, View

from core.constants import ROL_ADMIN
from core.mixins import RolRequeridoMixin

from .forms import LoginForm, PerfilForm, UsuarioCreateForm, UsuarioUpdateForm
from .models import Usuario


class LoginView(auth_views.LoginView):
    """Inicio de sesión del sistema (RF-01)."""

    template_name = "usuarios/login.html"
    authentication_form = LoginForm
    redirect_authenticated_user = True


class LogoutView(auth_views.LogoutView):
    next_page = reverse_lazy("usuarios:login")


class UsuarioListView(RolRequeridoMixin, ListView):
    """Listado y búsqueda de usuarios del sistema (RF-02, RF-10 aplicado a usuarios)."""

    model = Usuario
    template_name = "usuarios/usuario_list.html"
    context_object_name = "usuarios"
    paginate_by = 15
    roles_permitidos = [ROL_ADMIN]

    def get_queryset(self):
        qs = Usuario.objects.all().order_by("first_name", "last_name")
        buscar = self.request.GET.get("q", "").strip()
        rol = self.request.GET.get("rol", "").strip()
        estado = self.request.GET.get("estado", "").strip()

        if buscar:
            qs = qs.filter(
                Q(first_name__icontains=buscar)
                | Q(last_name__icontains=buscar)
                | Q(username__icontains=buscar)
                | Q(dni__icontains=buscar)
            )
        if rol:
            qs = qs.filter(rol=rol)
        if estado == "activo":
            qs = qs.filter(is_active=True)
        elif estado == "inactivo":
            qs = qs.filter(is_active=False)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["roles"] = Usuario._meta.get_field("rol").choices
        ctx["q"] = self.request.GET.get("q", "")
        ctx["rol_actual"] = self.request.GET.get("rol", "")
        ctx["estado_actual"] = self.request.GET.get("estado", "")
        return ctx


class UsuarioCreateView(RolRequeridoMixin, SuccessMessageMixin, CreateView):
    """Registro de nuevos usuarios y asignación de rol (RF-02, RF-03)."""

    model = Usuario
    form_class = UsuarioCreateForm
    template_name = "usuarios/usuario_form.html"
    success_url = reverse_lazy("usuarios:lista")
    success_message = "El usuario '%(username)s' fue registrado correctamente."
    roles_permitidos = [ROL_ADMIN]


class UsuarioUpdateView(RolRequeridoMixin, SuccessMessageMixin, UpdateView):
    """Edición de datos y rol de un usuario (RF-02, RF-03)."""

    model = Usuario
    form_class = UsuarioUpdateForm
    template_name = "usuarios/usuario_form.html"
    success_url = reverse_lazy("usuarios:lista")
    success_message = "Los datos del usuario fueron actualizados correctamente."
    roles_permitidos = [ROL_ADMIN]

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["usuario_actual"] = self.request.user
        return kwargs


class UsuarioToggleActivoView(RolRequeridoMixin, View):
    """Activa o desactiva una cuenta de usuario (RF-02)."""

    roles_permitidos = [ROL_ADMIN]

    def post(self, request, pk):
        usuario = get_object_or_404(Usuario, pk=pk)
        if usuario == request.user:
            messages.error(request, "No puede desactivar su propia cuenta.")
        else:
            usuario.is_active = not usuario.is_active
            usuario.save(update_fields=["is_active"])
            estado = "activada" if usuario.is_active else "desactivada"
            messages.success(request, f"La cuenta de {usuario.get_full_name()} fue {estado}.")
        return redirect("usuarios:lista")


class PerfilUpdateView(LoginRequiredMixin, SuccessMessageMixin, UpdateView):
    """Permite a cualquier usuario autenticado actualizar su propio perfil."""

    model = Usuario
    form_class = PerfilForm
    template_name = "usuarios/perfil_form.html"
    success_url = reverse_lazy("usuarios:perfil")
    success_message = "Su perfil fue actualizado correctamente."

    def get_object(self, queryset=None):
        return self.request.user


class CambiarPasswordView(SuccessMessageMixin, auth_views.PasswordChangeView):
    """Cambio de contraseña del usuario autenticado (RF-05)."""

    template_name = "usuarios/password_change.html"
    success_url = reverse_lazy("usuarios:perfil")
    success_message = "Su contraseña fue actualizada correctamente."


class RecuperarPasswordView(auth_views.PasswordResetView):
    """Recuperación de contraseña vía correo electrónico (RF-05)."""

    template_name = "usuarios/password_reset.html"
    email_template_name = "usuarios/password_reset_email.html"
    subject_template_name = "usuarios/password_reset_subject.txt"
    success_url = reverse_lazy("usuarios:password_reset_done")


class RecuperarPasswordDoneView(auth_views.PasswordResetDoneView):
    template_name = "usuarios/password_reset_done.html"


class RecuperarPasswordConfirmView(auth_views.PasswordResetConfirmView):
    template_name = "usuarios/password_reset_confirm.html"
    success_url = reverse_lazy("usuarios:password_reset_complete")


class RecuperarPasswordCompleteView(auth_views.PasswordResetCompleteView):
    template_name = "usuarios/password_reset_complete.html"
