from django.contrib import admin

from .models import AdicionalDeductivo, AmpliacionPlazo, CalendarioEjecucion


@admin.register(CalendarioEjecucion)
class CalendarioEjecucionAdmin(admin.ModelAdmin):
    list_display = ("obra", "periodo", "monto_programado", "avance_fisico_programado")
    search_fields = ("obra__codigo", "obra__nombre")


@admin.register(AmpliacionPlazo)
class AmpliacionPlazoAdmin(admin.ModelAdmin):
    list_display = ("obra", "numero", "fecha_solicitud", "dias_otorgados", "estado")
    list_filter = ("estado",)
    search_fields = ("obra__codigo", "obra__nombre")


@admin.register(AdicionalDeductivo)
class AdicionalDeductivoAdmin(admin.ModelAdmin):
    list_display = ("obra", "tipo", "numero", "monto", "estado")
    list_filter = ("tipo", "estado")
    search_fields = ("obra__codigo", "obra__nombre")
