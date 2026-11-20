from django.contrib import messages
from django.contrib.messages.views import SuccessMessageMixin
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from avances.models import asignar_ultimos_avances
from core.constants import ROL_ADMIN, ROL_ALTA_DIRECCION, ROL_APOYO, ROL_RESIDENTE, ROL_SUPERVISOR, ROLES_GESTION_OBRA
from core.mixins import RolRequeridoMixin

from .forms import ExpedienteTecnicoForm, FichaInfobrasForm, ObraForm, ParalizacionesFormSet, PartidasFormSet
from .models import ExpedienteTecnico, FichaInfobras, Obra


class ObraQuerysetPorRolMixin:
    """
    Aplica el filtro de visibilidad según el rol del usuario (RF-04):
    el residente y el supervisor solo ven, por defecto, las obras bajo su
    responsabilidad; el administrador, el personal administrativo de apoyo y la
    alta dirección visualizan la totalidad de las obras registradas.
    """

    def get_base_queryset(self):
        return Obra.visibles_para(self.request.user)


class ObraListView(ObraQuerysetPorRolMixin, RolRequeridoMixin, ListView):
    """Listado, búsqueda y filtrado de obras registradas (RF-10)."""

    model = Obra
    template_name = "obras/obra_list.html"
    context_object_name = "obras"
    paginate_by = 15
    roles_permitidos = [ROL_ADMIN, ROL_APOYO, ROL_RESIDENTE, ROL_SUPERVISOR, ROL_ALTA_DIRECCION]

    def get_queryset(self):
        qs = self.get_base_queryset()
        buscar = self.request.GET.get("q", "").strip()
        estado = self.request.GET.get("estado", "").strip()
        modalidad = self.request.GET.get("modalidad", "").strip()
        unidad = self.request.GET.get("unidad", "").strip()

        if buscar:
            qs = qs.filter(Q(nombre__icontains=buscar) | Q(codigo__icontains=buscar))
        if estado:
            qs = qs.filter(estado=estado)
        if modalidad:
            qs = qs.filter(modalidad_ejecucion=modalidad)
        if unidad:
            qs = qs.filter(unidad_organica__icontains=unidad)
        return qs.order_by("-fecha_registro")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["q"] = self.request.GET.get("q", "")
        ctx["estado_actual"] = self.request.GET.get("estado", "")
        ctx["modalidad_actual"] = self.request.GET.get("modalidad", "")
        ctx["unidad_actual"] = self.request.GET.get("unidad", "")
        ctx["estados"] = Obra._meta.get_field("estado").choices
        ctx["modalidades"] = Obra._meta.get_field("modalidad_ejecucion").choices
        ctx["unidades"] = Obra.unidades_visibles(self.request.user)
        # Las tarjetas muestran el avance de cada obra: se obtiene en una sola consulta (RNF-04)
        ctx["obras"] = list(ctx["page_obj"].object_list)
        asignar_ultimos_avances(ctx["obras"])
        return ctx


class ObraDetailView(ObraQuerysetPorRolMixin, RolRequeridoMixin, DetailView):
    """
    Ficha técnica completa de la obra: datos generales, expediente técnico,
    últimos avances, valorizaciones, calendario, modificaciones contractuales
    y documentos asociados (hub central del sistema).
    """

    model = Obra
    template_name = "obras/obra_detail.html"
    context_object_name = "obra"
    roles_permitidos = [ROL_ADMIN, ROL_APOYO, ROL_RESIDENTE, ROL_SUPERVISOR, ROL_ALTA_DIRECCION]

    def get_queryset(self):
        return self.get_base_queryset()

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        obra = self.object
        ctx["avances"] = obra.avances.all()[:12]
        ctx["valorizaciones"] = obra.valorizaciones.all()[:12]
        ctx["calendario"] = obra.calendario.all()
        ctx["ampliaciones"] = obra.ampliaciones_plazo.all()
        ctx["adicionales"] = obra.adicionales_deductivos.all()
        ctx["documentos"] = obra.documentos.select_related("tipo_documento").all()[:12]
        ctx["informes"] = obra.informes.all()[:12]
        try:
            ctx["expediente"] = obra.expediente_tecnico
        except ExpedienteTecnico.DoesNotExist:
            ctx["expediente"] = None
        ctx["ficha_infobras"] = FichaInfobras.objects.filter(obra=obra).first()
        ctx["paralizaciones"] = obra.paralizaciones.all()
        return ctx


class ObraCreateView(RolRequeridoMixin, SuccessMessageMixin, CreateView):
    """Registro de una nueva obra pública (RF-06)."""

    model = Obra
    form_class = ObraForm
    template_name = "obras/obra_form.html"
    success_message = "La obra '%(nombre)s' fue registrada correctamente."
    roles_permitidos = ROLES_GESTION_OBRA

    def form_valid(self, form):
        form.instance.creado_por = self.request.user
        return super().form_valid(form)


class ObraUpdateView(RolRequeridoMixin, SuccessMessageMixin, UpdateView):
    """Edición de la ficha técnica y del estado de la obra (RF-06, RF-08)."""

    model = Obra
    form_class = ObraForm
    template_name = "obras/obra_form.html"
    success_message = "Los datos de la obra fueron actualizados correctamente."
    roles_permitidos = ROLES_GESTION_OBRA


class ExpedienteTecnicoUpsertView(RolRequeridoMixin, SuccessMessageMixin, UpdateView):
    """
    Crea o actualiza el expediente técnico vinculado a la obra (RF-07) junto
    con sus partidas y metrados programados (RF-11).
    """

    model = ExpedienteTecnico
    form_class = ExpedienteTecnicoForm
    template_name = "obras/expediente_form.html"
    success_message = "El expediente técnico fue guardado correctamente."
    roles_permitidos = ROLES_GESTION_OBRA

    def get_object(self, queryset=None):
        # No se crea nada al solo abrir la página: el expediente nuevo se
        # guarda únicamente cuando el formulario se envía y es válido.
        self.obra = get_object_or_404(Obra, pk=self.kwargs["obra_pk"])
        try:
            return self.obra.expediente_tecnico
        except ExpedienteTecnico.DoesNotExist:
            return ExpedienteTecnico(
                obra=self.obra, fecha_aprobacion=self.obra.fecha_inicio, monto_expediente=self.obra.presupuesto_asignado
            )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["obra"] = self.obra
        if "partidas" not in ctx:
            ctx["partidas"] = PartidasFormSet(instance=self.object, prefix="partidas")
        return ctx

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        form = self.get_form()
        partidas = PartidasFormSet(request.POST, instance=self.object, prefix="partidas")
        if form.is_valid() and partidas.is_valid():
            with transaction.atomic():
                self.object = form.save()
                partidas.instance = self.object
                partidas.save()
            messages.success(request, self.success_message)
            return redirect(self.get_success_url())
        return self.render_to_response(self.get_context_data(form=form, partidas=partidas))

    def get_success_url(self):
        return reverse_lazy("obras:detalle", args=[self.obra.pk])


class FichaInfobrasUpsertView(RolRequeridoMixin, SuccessMessageMixin, UpdateView):
    """Datos que exige INFOBRAS y las paralizaciones de la obra (RF-28)."""

    model = FichaInfobras
    form_class = FichaInfobrasForm
    template_name = "obras/ficha_infobras_form.html"
    success_message = "Los datos para INFOBRAS fueron guardados correctamente."
    roles_permitidos = ROLES_GESTION_OBRA

    def get_object(self, queryset=None):
        # Igual que el expediente: no se crea nada hasta que el formulario se envía y es válido
        self.obra = get_object_or_404(Obra, pk=self.kwargs["obra_pk"])
        return FichaInfobras.objects.filter(obra=self.obra).first() or FichaInfobras(obra=self.obra)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["obra"] = self.obra
        ctx["secciones"] = ctx["form"].secciones()
        if "paralizaciones" not in ctx:
            ctx["paralizaciones"] = ParalizacionesFormSet(instance=self.obra, prefix="paralizaciones")
        return ctx

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        form = self.get_form()
        paralizaciones = ParalizacionesFormSet(request.POST, instance=self.obra, prefix="paralizaciones")
        if form.is_valid() and paralizaciones.is_valid():
            with transaction.atomic():
                form.save()
                paralizaciones.save()
            messages.success(request, self.success_message)
            return redirect("obras:detalle", pk=self.obra.pk)
        return self.render_to_response(self.get_context_data(form=form, paralizaciones=paralizaciones))
