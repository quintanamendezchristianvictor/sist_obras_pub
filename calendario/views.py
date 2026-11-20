from django.contrib.messages.views import SuccessMessageMixin
from django.db import transaction
from django.http import Http404
from django.urls import reverse_lazy
from django.views.generic import CreateView, ListView, UpdateView

from core.constants import ROL_ADMIN, ROL_ALTA_DIRECCION, ROL_APOYO, ROL_RESIDENTE, ROL_SUPERVISOR
from core.mixins import RolRequeridoMixin
from obras.mixins import ObraVisibleMixin

from .forms import (
    AdicionalDeductivoForm,
    AmpliacionPlazoForm,
    CalendarioEjecucionForm,
    ResolverAdicionalForm,
    ResolverAmpliacionForm,
)
from .models import AdicionalDeductivo, AmpliacionPlazo, CalendarioEjecucion

_TODOS_LOS_ROLES = [ROL_ADMIN, ROL_APOYO, ROL_RESIDENTE, ROL_SUPERVISOR, ROL_ALTA_DIRECCION]
_ROLES_GESTION = [ROL_ADMIN]


class FormularioConObraMixin:
    """Entrega la obra al formulario y la asigna al registro nuevo."""

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["obra"] = self.obra
        return kwargs

    def form_valid(self, form):
        form.instance.obra = self.obra
        if hasattr(form.instance, "registrado_por_id") and not form.instance.pk:
            form.instance.registrado_por = self.request.user
        return super().form_valid(form)


class CalendarioEjecucionListView(RolRequeridoMixin, ObraVisibleMixin, ListView):
    """Calendario de ejecución valorizado de la obra (RF-20)."""

    model = CalendarioEjecucion
    template_name = "calendario/calendario_list.html"
    context_object_name = "items"
    roles_permitidos = _TODOS_LOS_ROLES

    def get_queryset(self):
        return self.obra.calendario.all()

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        # Acumulados del calendario, para que se vea la curva programada completa
        acumulado_fisico = acumulado_monto = 0
        filas = []
        for item in ctx["items"]:
            acumulado_fisico += item.avance_fisico_programado
            acumulado_monto += item.monto_programado
            filas.append((item, acumulado_fisico, acumulado_monto))
        ctx["filas"] = filas
        return ctx


class CalendarioEjecucionCreateView(RolRequeridoMixin, ObraVisibleMixin, FormularioConObraMixin, SuccessMessageMixin, CreateView):
    model = CalendarioEjecucion
    form_class = CalendarioEjecucionForm
    template_name = "calendario/calendario_form.html"
    success_message = "El periodo del calendario de ejecución fue registrado."
    roles_permitidos = _ROLES_GESTION

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["titulo"] = "Registrar periodo del calendario de ejecución"
        return ctx

    def get_success_url(self):
        return reverse_lazy("calendario:lista", args=[self.obra.pk])


class CalendarioEjecucionUpdateView(RolRequeridoMixin, ObraVisibleMixin, FormularioConObraMixin, SuccessMessageMixin, UpdateView):
    """Corrección de un periodo del calendario de ejecución (RF-20)."""

    model = CalendarioEjecucion
    form_class = CalendarioEjecucionForm
    template_name = "calendario/calendario_form.html"
    success_message = "El periodo del calendario de ejecución fue actualizado."
    roles_permitidos = _ROLES_GESTION

    def get_queryset(self):
        return self.obra.calendario.all()

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["titulo"] = "Editar periodo del calendario de ejecución"
        return ctx

    def get_success_url(self):
        return reverse_lazy("calendario:lista", args=[self.obra.pk])


class AmpliacionPlazoListView(RolRequeridoMixin, ObraVisibleMixin, ListView):
    """Listado de ampliaciones de plazo de la obra (RF-21)."""

    model = AmpliacionPlazo
    template_name = "calendario/ampliacion_list.html"
    context_object_name = "ampliaciones"
    roles_permitidos = _TODOS_LOS_ROLES

    def get_queryset(self):
        return self.obra.ampliaciones_plazo.all()


class AmpliacionPlazoCreateView(RolRequeridoMixin, ObraVisibleMixin, FormularioConObraMixin, SuccessMessageMixin, CreateView):
    """Registro de la solicitud de ampliación de plazo (RF-21)."""

    model = AmpliacionPlazo
    form_class = AmpliacionPlazoForm
    template_name = "calendario/ampliacion_form.html"
    success_message = "La solicitud de ampliación de plazo fue registrada y queda pendiente de resolución."
    roles_permitidos = _ROLES_GESTION

    def get_success_url(self):
        return reverse_lazy("calendario:ampliaciones", args=[self.obra.pk])


class ResolverSolicitudMixin(RolRequeridoMixin, ObraVisibleMixin, SuccessMessageMixin):
    """
    Aprobación o rechazo de una solicitud pendiente (RF-21, RF-22). Una vez
    resuelta no puede volver a modificarse, para preservar la trazabilidad
    del plazo y presupuesto vigentes (RF-23).
    """

    template_name = "calendario/resolver_form.html"
    roles_permitidos = _ROLES_GESTION

    def get_object(self, queryset=None):
        objeto = super().get_object(queryset)
        if not objeto.pendiente:
            raise Http404("La solicitud ya fue resuelta.")
        return objeto


class AmpliacionPlazoResolverView(ResolverSolicitudMixin, UpdateView):
    model = AmpliacionPlazo
    form_class = ResolverAmpliacionForm
    success_message = "La ampliación de plazo fue resuelta; el plazo vigente de la obra se actualizó."

    def get_queryset(self):
        return self.obra.ampliaciones_plazo.all()

    def get_success_url(self):
        return reverse_lazy("calendario:ampliaciones", args=[self.obra.pk])


class AdicionalDeductivoListView(RolRequeridoMixin, ObraVisibleMixin, ListView):
    """Listado de adicionales y deductivos de obra (RF-22)."""

    model = AdicionalDeductivo
    template_name = "calendario/adicional_list.html"
    context_object_name = "adicionales"
    roles_permitidos = _TODOS_LOS_ROLES

    def get_queryset(self):
        return self.obra.adicionales_deductivos.all()


class AdicionalDeductivoCreateView(RolRequeridoMixin, ObraVisibleMixin, FormularioConObraMixin, SuccessMessageMixin, CreateView):
    """Registro de la solicitud de adicional o deductivo de obra (RF-22)."""

    model = AdicionalDeductivo
    form_class = AdicionalDeductivoForm
    template_name = "calendario/adicional_form.html"
    success_message = "El adicional/deductivo fue registrado y queda pendiente de resolución."
    roles_permitidos = _ROLES_GESTION

    def get_success_url(self):
        return reverse_lazy("calendario:adicionales", args=[self.obra.pk])


class AdicionalDeductivoResolverView(ResolverSolicitudMixin, UpdateView):
    model = AdicionalDeductivo
    form_class = ResolverAdicionalForm
    success_message = "El adicional/deductivo fue resuelto; el presupuesto vigente de la obra se actualizó."

    def get_queryset(self):
        return self.obra.adicionales_deductivos.all()

    def form_valid(self, form):
        # El presupuesto vigente cambia al aprobarse: se actualiza el avance financiero vigente (RF-23)
        with transaction.atomic():
            respuesta = super().form_valid(form)
            self.obra.actualizar_financiero_vigente()
        return respuesta

    def get_success_url(self):
        return reverse_lazy("calendario:adicionales", args=[self.obra.pk])
