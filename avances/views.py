from django.contrib import messages
from django.contrib.messages.views import SuccessMessageMixin
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from core.constants import ROL_ADMIN, ROL_ALTA_DIRECCION, ROL_APOYO, ROL_RESIDENTE, ROL_SUPERVISOR
from core.mixins import RolRequeridoMixin
from obras.mixins import ObraVisibleMixin
from obras.models import Obra

from .forms import AvanceObraForm, EvidenciaAvanceForm
from .models import AvanceObra


def _avances_visibles(usuario):
    """Avances de las obras que el usuario puede consultar según su rol (RF-04)."""
    return AvanceObra.objects.filter(obra__in=Obra.visibles_para(usuario))


class AvanceListView(RolRequeridoMixin, ObraVisibleMixin, ListView):
    """Historial de avances físicos y financieros registrados para una obra (RF-11 a RF-14)."""

    model = AvanceObra
    template_name = "avances/avance_list.html"
    context_object_name = "avances"
    paginate_by = 15
    roles_permitidos = [ROL_ADMIN, ROL_APOYO, ROL_RESIDENTE, ROL_SUPERVISOR, ROL_ALTA_DIRECCION]

    def get_queryset(self):
        return self.obra.avances.all()


class AvanceCreateView(RolRequeridoMixin, ObraVisibleMixin, SuccessMessageMixin, CreateView):
    """Registro de un nuevo avance periódico (RF-11, RF-12, RF-13, RF-14)."""

    model = AvanceObra
    form_class = AvanceObraForm
    template_name = "avances/avance_form.html"
    success_message = "El avance del periodo fue registrado correctamente."
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
        return reverse_lazy("avances:detalle", args=[self.object.pk])


class AvanceUpdateView(RolRequeridoMixin, SuccessMessageMixin, UpdateView):
    """
    Corrección del último avance registrado de la obra (RNF-19: permite
    subsanar un error de digitación sin perder la información registrada).
    Solo el último periodo es editable para no alterar la secuencia histórica.
    """

    model = AvanceObra
    form_class = AvanceObraForm
    template_name = "avances/avance_form.html"
    success_message = "El avance del periodo fue corregido correctamente."
    roles_permitidos = [ROL_RESIDENTE]

    def get_queryset(self):
        return _avances_visibles(self.request.user).select_related("obra")

    def get_object(self, queryset=None):
        avance = super().get_object(queryset)
        if avance != avance.obra.ultimo_avance:
            raise Http404("Solo se puede corregir el último avance registrado de la obra.")
        return avance

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["obra"] = self.object.obra
        return kwargs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["obra"] = self.object.obra
        return ctx

    def get_success_url(self):
        return reverse_lazy("avances:detalle", args=[self.object.pk])


class AvanceDetailView(RolRequeridoMixin, DetailView):
    """Detalle de un avance periódico, con sus evidencias fotográficas (RF-15)."""

    model = AvanceObra
    template_name = "avances/avance_detail.html"
    context_object_name = "avance"
    roles_permitidos = [ROL_ADMIN, ROL_APOYO, ROL_RESIDENTE, ROL_SUPERVISOR, ROL_ALTA_DIRECCION]

    def get_queryset(self):
        return _avances_visibles(self.request.user)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["evidencias"] = self.object.evidencias.all()
        ctx["metrados"] = self.object.metrados.select_related("partida")
        ctx["es_ultimo"] = self.object == self.object.obra.ultimo_avance
        ctx["form_evidencia"] = EvidenciaAvanceForm()
        return ctx


class EvidenciaCreateView(RolRequeridoMixin, View):
    """Carga de evidencia fotográfica a un registro de avance (RF-15)."""

    roles_permitidos = [ROL_RESIDENTE]

    def post(self, request, *args, **kwargs):
        avance = get_object_or_404(_avances_visibles(request.user), pk=kwargs["avance_pk"])
        form = EvidenciaAvanceForm(request.POST, request.FILES)
        if form.is_valid():
            evidencia = form.save(commit=False)
            evidencia.avance = avance
            evidencia.save()
            messages.success(request, "La evidencia fotográfica fue cargada correctamente.")
        else:
            errores = " ".join(error for lista in form.errors.values() for error in lista)
            messages.error(request, f"No se pudo cargar la evidencia. {errores}")
        return redirect("avances:detalle", pk=avance.pk)
