from django.contrib import admin

from .models import Documento, TipoDocumento


@admin.register(TipoDocumento)
class TipoDocumentoAdmin(admin.ModelAdmin):
    list_display = ("nombre",)
    search_fields = ("nombre",)


@admin.register(Documento)
class DocumentoAdmin(admin.ModelAdmin):
    list_display = ("nombre", "obra", "tipo_documento", "periodo", "subido_por", "fecha_carga")
    list_filter = ("tipo_documento",)
    search_fields = ("nombre", "obra__codigo", "obra__nombre")
