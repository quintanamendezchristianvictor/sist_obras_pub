from django.contrib import admin

from .models import Bitacora, Configuracion


@admin.register(Bitacora)
class BitacoraAdmin(admin.ModelAdmin):
    list_display = ("fecha", "usuario", "accion", "modulo", "detalle", "direccion_ip")
    list_filter = ("accion", "modulo", "fecha")
    search_fields = ("usuario__username", "usuario__first_name", "usuario__last_name", "ruta")
    date_hierarchy = "fecha"
    ordering = ("-fecha",)

    def has_add_permission(self, request):
        # La bitácora solo se genera automáticamente, nunca manualmente.
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(Configuracion)
class ConfiguracionAdmin(admin.ModelAdmin):
    list_display = ("nombre_sistema", "nombre_entidad", "umbral_riesgo", "umbral_atraso")

    def has_add_permission(self, request):
        return not Configuracion.objects.exists()
