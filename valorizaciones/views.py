from django.contrib.messages.views import SuccessMessageMixin
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import CreateView, DetailView, ListView, UpdateView, View

from core.constants import ROL_ADMIN, ROL_ALTA_DIRECCION, ROL_APOYO, ROL_RESIDENTE, ROL_SUPERVISOR
from core.mixins import RolRequeridoMixin
from core.utils import render_to_pdf
from obras.mixins import ObraVisibleMixin
from obras.models import Obra

from .forms import InformeMensualForm, ValorizacionForm, ValorizacionRevisionForm
from .models import (
    ESTADO_REGISTRADA,
    TIPO_INFORME_RESIDENTE,
    TIPO_INFORME_SUPERVISOR,
    InformeMensual,
    Valorizacion,
)

_TODOS_LOS_ROLES = [ROL_ADMIN, ROL_APOYO, ROL_RESIDENTE, ROL_SUPERVISOR, ROL_ALTA_DIRECCION]

# Tipo de informe que elabora cada rol (RF-17)
_TIPO_INFORME_POR_ROL = {ROL_RESIDENTE: TIPO_INFORME_RESIDENTE, ROL_SUPERVISOR: TIPO_INFORME_SUPERVISOR}


def _valorizaciones_visibles(usuario):
    return Valorizacion.objects.filter(obra__in=Obra.visibles_para(usuario)).select_related("obra")


def _informes_visibles(usuario):
    return InformeMensual.objects.filter(obra__in=Obra.visibles_para(usuario)).select_related("obra", "elaborado_por")


class ValorizacionListView(RolRequeridoMixin, ObraVisibleMixin, ListView):
    """Listado de valorizaciones de una obra (RF-16)."""

    model = Valorizacion
    template_name = "valorizaciones/valorizacion_list.html"
    context_object_name = "valorizaciones"
    roles_permitidos = _TODOS_LOS_ROLES

    def get_queryset(self):
        return self.obra.valorizaciones.all()


class ValorizacionCreateView(RolRequeridoMixin, ObraVisibleMixin, SuccessMessageMixin, CreateView):
    """Registro de una valorización mensual por el residente (RF-16, RF-19)."""

    model = Valorizacion
    form_class = ValorizacionForm
    template_name = "valorizaciones/valorizacion_form.html"
    success_message = "La valorización fue registrada y queda pendiente de revisión del supervisor."
    roles_permitidos = [ROL_RESIDENTE]

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["obra"] = self.obra
        return kwargs

    def form_valid(self, form):
        form.instance.obra = self.obra
        form.instance.registrado_por = self.request.user
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy("valorizaciones:lista", args=[self.obra.pk])


class ValorizacionSubsanarView(RolRequeridoMixin, SuccessMessageMixin, UpdateView):
    """
    Corrección de una valorización observada por el residente (RF-19): al
    guardarla vuelve al estado "Registrada" para una nueva revisión.
    """

    model = Valorizacion
    form_class = ValorizacionForm
    template_name = "valorizaciones/valorizacion_form.html"
    success_message = "La valorización fue corregida y enviada nuevamente a revisión."
    roles_permitidos = [ROL_RESIDENTE]

    def get_queryset(self):
        return _valorizaciones_visibles(self.request.user)

    def get_object(self, queryset=None):
        valorizacion = super().get_object(queryset)
        if not valorizacion.observada:
            raise Http404("Solo se pueden corregir valorizaciones observadas.")
        return valorizacion

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["obra"] = self.object.obra
        return kwargs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["obra"] = self.object.obra
        return ctx

    def form_valid(self, form):
        form.instance.estado = ESTADO_REGISTRADA
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy("valorizaciones:lista", args=[self.object.obra.pk])


class ValorizacionRevisarView(RolRequeridoMixin, SuccessMessageMixin, UpdateView):
    """
    Revisión de una valorización por el supervisor/inspector de la obra
    (RF-19): la aprueba o la observa. Solo procede sobre valorizaciones
    pendientes; la validación corresponde exclusivamente al supervisor.
    """

    model = Valorizacion
    form_class = ValorizacionRevisionForm
    template_name = "valorizaciones/valorizacion_revisar.html"
    success_message = "La revisión de la valorización fue registrada."
    roles_permitidos = [ROL_SUPERVISOR]
    permitir_admin = False

    def get_queryset(self):
        # El supervisor solo revisa valorizaciones de las obras a su cargo (RF-04)
        return _valorizaciones_visibles(self.request.user)

    def get_object(self, queryset=None):
        valorizacion = super().get_object(queryset)
        if not valorizacion.pendiente:
            raise Http404("La valorización ya fue revisada.")
        return valorizacion

    def form_valid(self, form):
        form.instance.revisado_por = self.request.user
        form.instance.fecha_revision = timezone.now()
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy("valorizaciones:lista", args=[self.object.obra.pk])


class ValorizacionExportarPDFView(RolRequeridoMixin, View):
    """Exportación de la valorización en formato PDF (RF-18)."""

    roles_permitidos = _TODOS_LOS_ROLES

    def get(self, request, pk):
        valorizacion = get_object_or_404(_valorizaciones_visibles(request.user), pk=pk)
        contexto = {"valorizacion": valorizacion, "obra": valorizacion.obra, "fecha_emision": timezone.now()}
        nombre = f"valorizacion_{valorizacion.obra.codigo}_{valorizacion.numero}.pdf"
        return render_to_pdf("valorizaciones/valorizacion_pdf.html", contexto, nombre)


class InformeMensualListView(RolRequeridoMixin, ObraVisibleMixin, ListView):
    """Listado de informes mensuales de una obra (RF-17)."""

    model = InformeMensual
    template_name = "valorizaciones/informe_list.html"
    context_object_name = "informes"
    roles_permitidos = _TODOS_LOS_ROLES

    def get_queryset(self):
        return self.obra.informes.select_related("elaborado_por")


class InformeMensualCreateView(RolRequeridoMixin, ObraVisibleMixin, SuccessMessageMixin, CreateView):
    """Generación del informe mensual del residente o del supervisor (RF-17)."""

    model = InformeMensual
    form_class = InformeMensualForm
    template_name = "valorizaciones/informe_form.html"
    success_message = "El informe mensual fue generado con los datos registrados del periodo."
    roles_permitidos = [ROL_RESIDENTE, ROL_SUPERVISOR]

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["obra"] = self.obra
        kwargs["tipo"] = _TIPO_INFORME_POR_ROL.get(self.request.user.rol)
        return kwargs

    def form_valid(self, form):
        form.instance.obra = self.obra
        form.instance.elaborado_por = self.request.user
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy("valorizaciones:informe_detalle", args=[self.object.pk])


class InformeMensualDetailView(RolRequeridoMixin, DetailView):
    """Vista previa del informe mensual con los datos del periodo (RF-17)."""

    model = InformeMensual
    template_name = "valorizaciones/informe_detail.html"
    context_object_name = "informe"
    roles_permitidos = _TODOS_LOS_ROLES

    def get_queryset(self):
        return _informes_visibles(self.request.user)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["obra"] = self.object.obra
        ctx["datos"] = self.object.datos_periodo()
        return ctx


class InformeMensualExportarPDFView(RolRequeridoMixin, View):
    """Exportación del informe mensual en formato PDF (RF-18)."""

    roles_permitidos = _TODOS_LOS_ROLES

    def get(self, request, pk):
        informe = get_object_or_404(_informes_visibles(request.user), pk=pk)
        contexto = {
            "informe": informe,
            "obra": informe.obra,
            "datos": informe.datos_periodo(),
            "fecha_emision": timezone.now(),
        }
        nombre = f"informe_{informe.obra.codigo}_{informe.periodo:%Y_%m}.pdf"
        return render_to_pdf("valorizaciones/informe_pdf.html", contexto, nombre)
