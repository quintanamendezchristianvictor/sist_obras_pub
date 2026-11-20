from django.contrib import admin

from .models import InformeMensual, Valorizacion


@admin.register(Valorizacion)
class ValorizacionAdmin(admin.ModelAdmin):
    list_display = ("obra", "numero", "periodo", "monto", "estado", "revisado_por")
    list_filter = ("estado", "periodo")
    search_fields = ("obra__codigo", "obra__nombre")


@admin.register(InformeMensual)
class InformeMensualAdmin(admin.ModelAdmin):
    list_display = ("obra", "tipo", "periodo", "elaborado_por")
    list_filter = ("tipo", "periodo")
    search_fields = ("obra__codigo", "obra__nombre")
