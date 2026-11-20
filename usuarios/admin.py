from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Usuario


@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    model = Usuario
    list_display = ("username", "first_name", "last_name", "rol", "unidad_organica", "is_active", "is_staff")
    list_filter = ("rol", "is_active", "is_staff")
    search_fields = ("username", "first_name", "last_name", "dni", "email")
    fieldsets = UserAdmin.fieldsets + (
        ("Datos del sistema de obras", {
            "fields": ("rol", "sexo", "dni", "telefono", "cargo", "unidad_organica"),
        }),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ("Datos del sistema de obras", {
            "fields": ("rol", "sexo", "dni", "telefono", "cargo", "unidad_organica"),
        }),
    )
