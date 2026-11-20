from django import forms
from django.conf import settings
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.core.cache import cache

from core.constants import ROL_ADMIN

from .models import Usuario

_WIDGET_CLASS = "form-control"
_SELECT_CLASS = "form-select"


class LoginForm(AuthenticationForm):
    """Formulario de inicio de sesión (RF-01)."""

    username = forms.CharField(
        label="Usuario",
        widget=forms.TextInput(attrs={"class": _WIDGET_CLASS, "autofocus": True, "placeholder": "Usuario"}),
    )
    password = forms.CharField(
        label="Contraseña",
        widget=forms.PasswordInput(attrs={"class": _WIDGET_CLASS, "placeholder": "Contraseña"}),
    )

    error_messages = {
        "invalid_login": "Usuario o contraseña incorrectos. Verifique sus credenciales e intente nuevamente.",
        "inactive": "Esta cuenta se encuentra desactivada. Comuníquese con el administrador del sistema.",
    }

    def _clave_intentos(self):
        ip = self.request.META.get("REMOTE_ADDR", "") if self.request else ""
        return f"login_intentos:{self.cleaned_data.get('username', '').lower()}:{ip}"

    def clean(self):
        """RNF-17: tras varios intentos fallidos se bloquea temporalmente esa cuenta desde esa dirección."""
        clave = self._clave_intentos()
        intentos = cache.get(clave, 0)
        if intentos >= settings.LOGIN_INTENTOS_MAX:
            minutos = settings.LOGIN_BLOQUEO_SEGUNDOS // 60
            raise forms.ValidationError(f"Demasiados intentos fallidos. Vuelva a intentarlo en {minutos} minutos.", code="bloqueado")
        try:
            datos = super().clean()
        except forms.ValidationError:
            cache.set(clave, intentos + 1, settings.LOGIN_BLOQUEO_SEGUNDOS)
            raise
        cache.delete(clave)
        return datos


class UsuarioCreateForm(UserCreationForm):
    """Registro de nuevos usuarios por parte del administrador (RF-02)."""

    class Meta:
        model = Usuario
        fields = [
            "username", "first_name", "last_name", "email", "sexo", "dni",
            "telefono", "cargo", "unidad_organica", "rol",
        ]
        widgets = {
            "username": forms.TextInput(attrs={"class": _WIDGET_CLASS}),
            "first_name": forms.TextInput(attrs={"class": _WIDGET_CLASS}),
            "last_name": forms.TextInput(attrs={"class": _WIDGET_CLASS}),
            "email": forms.EmailInput(attrs={"class": _WIDGET_CLASS}),
            "sexo": forms.Select(attrs={"class": _SELECT_CLASS}),
            "dni": forms.TextInput(attrs={"class": _WIDGET_CLASS, "maxlength": 8}),
            "telefono": forms.TextInput(attrs={"class": _WIDGET_CLASS}),
            "cargo": forms.TextInput(attrs={"class": _WIDGET_CLASS}),
            "unidad_organica": forms.TextInput(attrs={"class": _WIDGET_CLASS}),
            "rol": forms.Select(attrs={"class": _SELECT_CLASS}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["password1"].widget.attrs.update({"class": _WIDGET_CLASS})
        self.fields["password2"].widget.attrs.update({"class": _WIDGET_CLASS})


class UsuarioUpdateForm(forms.ModelForm):
    """Edición de datos y rol de un usuario existente (RF-02, RF-03)."""

    class Meta:
        model = Usuario
        fields = [
            "first_name", "last_name", "email", "sexo", "dni", "telefono",
            "cargo", "unidad_organica", "rol", "is_active",
        ]
        widgets = {
            "first_name": forms.TextInput(attrs={"class": _WIDGET_CLASS}),
            "last_name": forms.TextInput(attrs={"class": _WIDGET_CLASS}),
            "email": forms.EmailInput(attrs={"class": _WIDGET_CLASS}),
            "sexo": forms.Select(attrs={"class": _SELECT_CLASS}),
            "dni": forms.TextInput(attrs={"class": _WIDGET_CLASS, "maxlength": 8}),
            "telefono": forms.TextInput(attrs={"class": _WIDGET_CLASS}),
            "cargo": forms.TextInput(attrs={"class": _WIDGET_CLASS}),
            "unidad_organica": forms.TextInput(attrs={"class": _WIDGET_CLASS}),
            "rol": forms.Select(attrs={"class": _SELECT_CLASS}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def __init__(self, *args, usuario_actual=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.usuario_actual = usuario_actual

    def clean(self):
        """El administrador no puede quitarse a sí mismo el acceso y dejar el sistema sin gestión."""
        datos = super().clean()
        if self.instance == self.usuario_actual:
            if datos.get("rol") != ROL_ADMIN:
                self.add_error("rol", "No puede cambiar su propio rol de administrador.")
            if not datos.get("is_active"):
                self.add_error("is_active", "No puede desactivar su propia cuenta.")
        return datos


class PerfilForm(forms.ModelForm):
    """Permite a cualquier usuario autenticado editar su propia información de contacto."""

    class Meta:
        model = Usuario
        fields = ["first_name", "last_name", "email", "sexo", "telefono"]
        widgets = {
            "first_name": forms.TextInput(attrs={"class": _WIDGET_CLASS}),
            "last_name": forms.TextInput(attrs={"class": _WIDGET_CLASS}),
            "email": forms.EmailInput(attrs={"class": _WIDGET_CLASS}),
            "sexo": forms.Select(attrs={"class": _SELECT_CLASS}),
            "telefono": forms.TextInput(attrs={"class": _WIDGET_CLASS}),
        }
