from django.conf import settings
from django.core.cache import cache
from django.http import HttpResponse, JsonResponse
from django.template.loader import render_to_string
from django.utils import timezone
from django.views import View
from django.views.generic import TemplateView

from core.constants import ROL_ADMIN, ROL_ALTA_DIRECCION, ROL_APOYO, ROL_RESIDENTE, ROL_SUPERVISOR
from core.mixins import RolRequeridoMixin
from core.pdf import html_a_pdf
from core.utils import respuesta_pdf
from obras.models import Obra

from .excel import construir_libro
from .services import aplicar_filtros, construir_datos_dashboard, firma_de_datos, indicadores_por_obra, leer_periodo

_TODOS_LOS_ROLES = [ROL_ADMIN, ROL_APOYO, ROL_RESIDENTE, ROL_SUPERVISOR, ROL_ALTA_DIRECCION]


class DashboardView(RolRequeridoMixin, TemplateView):
    """
    Dashboard dinámico del sistema (RF-29 a RF-32): indicadores clave (KPI),
    gráficos de avance físico-financiero y alertas de obras en riesgo,
    dirigido principalmente a la alta dirección pero visible para todos los
    roles con la información que les corresponde.
    """

    template_name = "reportes/dashboard.html"
    roles_permitidos = _TODOS_LOS_ROLES

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["datos"] = construir_datos_dashboard(self.request)
        ctx["obras"] = Obra.visibles_para(self.request.user).select_related(None).only("pk", "codigo", "nombre").order_by("codigo")
        ctx["estados"] = Obra._meta.get_field("estado").choices
        ctx["unidades"] = Obra.unidades_visibles(self.request.user)
        ctx["obra_actual"] = self.request.GET.get("obra", "")
        ctx["estado_actual"] = self.request.GET.get("estado", "")
        ctx["unidad_actual"] = self.request.GET.get("unidad", "")
        ctx["periodo_actual"] = self.request.GET.get("periodo", "")
        return ctx


class DashboardDataAPIView(RolRequeridoMixin, View):
    """
    Endpoint JSON consumido por el JavaScript del dashboard para refrescar
    los indicadores y los gráficos sin recargar la página (RF-31), cada vez
    que el usuario cambia un filtro (RF-30) o se registra nueva información.
    """

    roles_permitidos = _TODOS_LOS_ROLES

    def get(self, request):
        return JsonResponse(construir_datos_dashboard(request))


class DashboardFirmaAPIView(RolRequeridoMixin, View):
    """
    Endpoint mínimo que el dashboard consulta periódicamente para saber si
    se registró información nueva (RF-31); solo entonces descarga los datos
    completos, ahorrando ancho de banda (RNF-08).
    """

    roles_permitidos = _TODOS_LOS_ROLES

    def get(self, request):
        return JsonResponse({"firma": firma_de_datos()})


class ReporteConsolidadoPDFView(RolRequeridoMixin, View):
    """
    Reporte consolidado de avance físico y financiero en PDF (RF-27). Generarlo
    es la operación más costosa del sistema: mientras nadie registre información
    nueva, el mismo reporte se reutiliza en lugar de volver a generarse (RNF-05).
    """

    roles_permitidos = _TODOS_LOS_ROLES

    def get(self, request):
        clave = f"reporte_pdf:{firma_de_datos()}:{request.user.pk}:{request.GET.urlencode()}"
        contenido = cache.get(clave)
        if contenido is None:
            corte = leer_periodo(request)
            contexto = {
                "filas": indicadores_por_obra(aplicar_filtros(request).order_by("codigo"), corte),
                "periodo": corte,
                "fecha_emision": timezone.now(),
                "usuario": request.user,
            }
            contenido = html_a_pdf(render_to_string("reportes/reporte_consolidado_pdf.html", contexto))
            if contenido is None:
                return HttpResponse("Ocurrió un error al generar el documento PDF.", status=500)
            cache.set(clave, contenido, settings.REPORTE_PDF_CACHE_SEGUNDOS)
        return respuesta_pdf(contenido, "reporte_consolidado_obras.pdf")


class ReporteConsolidadoExcelView(RolRequeridoMixin, View):
    """
    Reporte consolidado en Excel (RF-27) con la estructura de la información
    que exige INFOBRAS (RF-28): ver reportes/excel.py.
    """

    roles_permitidos = _TODOS_LOS_ROLES

    def get(self, request):
        corte = leer_periodo(request)
        libro = construir_libro(indicadores_por_obra(aplicar_filtros(request).order_by("codigo"), corte), corte)
        response = HttpResponse(content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        response["Content-Disposition"] = 'attachment; filename="reporte_consolidado_obras.xlsx"'
        libro.save(response)
        return response
