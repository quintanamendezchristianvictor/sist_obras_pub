from datetime import datetime

from django.contrib.messages.views import SuccessMessageMixin
from django.db.models import Q
from django.urls import reverse_lazy
from django.views.generic import CreateView, ListView

from core.constants import ROL_ADMIN, ROL_ALTA_DIRECCION, ROL_APOYO, ROL_RESIDENTE, ROL_SUPERVISOR
from core.mixins import RolRequeridoMixin
from obras.mixins import ObraVisibleMixin
from obras.models import Obra

from .forms import DocumentoForm
from .models import Documento, TipoDocumento

_TODOS_LOS_ROLES = [ROL_ADMIN, ROL_APOYO, ROL_RESIDENTE, ROL_SUPERVISOR, ROL_ALTA_DIRECCION]


class FiltroDocumentosMixin:
    """
    Filtros de búsqueda del acervo documentario (RF-25, RF-26): texto (en
    nombre y descripción), tipo de documento y periodo (AAAA-MM).
    """

    template_name = "documentos/documento_list.html"
    context_object_name = "documentos"
    paginate_by = 15

    def filtrar(self, qs):
        buscar = self.request.GET.get("q", "").strip()
        tipo = self.request.GET.get("tipo", "").strip()
        periodo = self.request.GET.get("periodo", "").strip()
        if buscar:
            qs = qs.filter(Q(nombre__icontains=buscar) | Q(descripcion__icontains=buscar))
        if tipo.isdigit():
            qs = qs.filter(tipo_documento_id=tipo)
        try:
            mes = datetime.strptime(periodo, "%Y-%m").date()
            qs = qs.filter(periodo__year=mes.year, periodo__month=mes.month)
        except ValueError:
            pass
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["q"] = self.request.GET.get("q", "")
        ctx["tipos"] = TipoDocumento.objects.all()
        ctx["tipo_actual"] = self.request.GET.get("tipo", "")
        ctx["periodo_actual"] = self.request.GET.get("periodo", "")
        return ctx


class DocumentoListView(RolRequeridoMixin, ObraVisibleMixin, FiltroDocumentosMixin, ListView):
    """Búsqueda y listado de documentos del acervo documentario de una obra (RF-26)."""

    model = Documento
    roles_permitidos = _TODOS_LOS_ROLES

    def get_queryset(self):
        return self.filtrar(self.obra.documentos.select_related("tipo_documento", "subido_por"))


class DocumentoBuscarView(RolRequeridoMixin, FiltroDocumentosMixin, ListView):
    """
    Búsqueda general en el acervo documentario de todas las obras que el
    usuario puede consultar según su rol (RF-26, RF-04).
    """

    model = Documento
    roles_permitidos = _TODOS_LOS_ROLES

    def get_queryset(self):
        qs = Documento.objects.filter(obra__in=Obra.visibles_para(self.request.user)).select_related(
            "tipo_documento", "subido_por", "obra"
        )
        obra = self.request.GET.get("obra", "").strip()
        if obra.isdigit():
            qs = qs.filter(obra_id=obra)
        return self.filtrar(qs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["obras"] = Obra.visibles_para(self.request.user).select_related(None).only("pk", "codigo", "nombre").order_by("codigo")
        ctx["obra_actual"] = self.request.GET.get("obra", "")
        return ctx


class DocumentoCreateView(RolRequeridoMixin, ObraVisibleMixin, SuccessMessageMixin, CreateView):
    """Carga de un nuevo documento al acervo documentario (RF-24, RF-25)."""

    model = Documento
    form_class = DocumentoForm
    template_name = "documentos/documento_form.html"
    success_message = "El documento fue cargado correctamente al acervo documentario."
    roles_permitidos = [ROL_ADMIN, ROL_APOYO]

    def form_valid(self, form):
        form.instance.obra = self.obra
        form.instance.subido_por = self.request.user
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy("documentos:lista", args=[self.obra.pk])
