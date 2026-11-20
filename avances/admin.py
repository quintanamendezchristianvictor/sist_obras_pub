from django.contrib import admin

from .models import AvanceObra, EvidenciaAvance


class EvidenciaInline(admin.TabularInline):
    model = EvidenciaAvance
    extra = 0


@admin.register(AvanceObra)
class AvanceObraAdmin(admin.ModelAdmin):
    list_display = (
        "obra", "periodo", "avance_fisico_programado_acum", "avance_fisico_ejecutado_acum",
        "avance_financiero_programado_acum", "avance_financiero_ejecutado_acum",
    )
    list_filter = ("periodo",)
    search_fields = ("obra__codigo", "obra__nombre")
    inlines = [EvidenciaInline]
