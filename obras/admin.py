from django.contrib import admin

from .models import ExpedienteTecnico, FichaInfobras, Obra, ParalizacionObra, PartidaExpediente


@admin.register(Obra)
class ObraAdmin(admin.ModelAdmin):
    list_display = ("codigo", "nombre", "estado", "modalidad_ejecucion", "residente", "supervisor", "presupuesto_asignado")
    list_filter = ("estado", "modalidad_ejecucion", "unidad_organica")
    search_fields = ("codigo", "nombre")


@admin.register(FichaInfobras)
class FichaInfobrasAdmin(admin.ModelAdmin):
    list_display = ("obra", "naturaleza", "contrato_numero", "recepcion_fecha", "liquidacion_fecha")
    search_fields = ("obra__codigo", "obra__nombre", "contrato_numero")


@admin.register(ParalizacionObra)
class ParalizacionObraAdmin(admin.ModelAdmin):
    list_display = ("obra", "fecha_inicio", "fecha_fin", "motivo")
    search_fields = ("obra__codigo", "motivo")


class PartidaExpedienteInline(admin.TabularInline):
    model = PartidaExpediente
    extra = 0


@admin.register(ExpedienteTecnico)
class ExpedienteTecnicoAdmin(admin.ModelAdmin):
    inlines = [PartidaExpedienteInline]
    list_display = ("numero_expediente", "obra", "fecha_aprobacion", "monto_expediente")
    search_fields = ("numero_expediente", "obra__nombre")
