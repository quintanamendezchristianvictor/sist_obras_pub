from django.apps import apps
from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import Http404
from django.views import View
from django.views.generic import ListView
from django.views.static import serve

from obras.models import Obra

from .constants import ROL_ADMIN, ROLES_CAMPO
from .mixins import RolRequeridoMixin
from .models import Bitacora

# Campos con archivos subidos y la relación que lleva desde el registro hasta su obra (RF-04)
_ARCHIVOS_DE_OBRA = [
    ("documentos.Documento", "archivo", "obra"),
    ("obras.ExpedienteTecnico", "archivo", "obra"),
    ("avances.EvidenciaAvance", "imagen", "avance__obra"),
    ("valorizaciones.Valorizacion", "archivo_pdf", "obra"),
    ("valorizaciones.InformeMensual", "archivo", "obra"),
    ("calendario.AmpliacionPlazo", "documento_sustento", "obra"),
    ("calendario.AdicionalDeductivo", "documento_sustento", "obra"),
]


class BitacoraListView(RolRequeridoMixin, ListView):
    """
    Consulta de la bitácora de operaciones críticas del sistema (RNF-16),
    disponible únicamente para el administrador del sistema.
    """

    model = Bitacora
    template_name = "core/bitacora_list.html"
    context_object_name = "registros"
    paginate_by = 25
    roles_permitidos = [ROL_ADMIN]

    def get_queryset(self):
        qs = Bitacora.objects.select_related("usuario").all()
        usuario = self.request.GET.get("usuario", "").strip()
        accion = self.request.GET.get("accion", "").strip()
        if usuario:
            qs = qs.filter(usuario_id=usuario)
        if accion:
            qs = qs.filter(accion=accion)
        return qs

    def get_context_data(self, **kwargs):
        from usuarios.models import Usuario

        ctx = super().get_context_data(**kwargs)
        ctx["usuarios"] = Usuario.objects.all().order_by("first_name")
        ctx["usuario_actual"] = self.request.GET.get("usuario", "")
        ctx["accion_actual"] = self.request.GET.get("accion", "")
        return ctx


class ArchivoProtegidoView(LoginRequiredMixin, View):
    """
    Entrega los archivos subidos al sistema (expedientes, evidencias,
    documentos del acervo, sustentos) solo a usuarios autenticados (RNF-17),
    en lugar de publicarlos como archivos estáticos accesibles por cualquiera.
    El residente y el supervisor solo reciben los archivos de sus obras, igual
    que en el resto del sistema (RF-04). `serve` impide salir de MEDIA_ROOT
    con rutas del tipo "../".
    """

    def get(self, request, ruta):
        if request.user.rol in ROLES_CAMPO and not self._archivo_visible(request.user, ruta):
            raise Http404("Archivo no disponible.")
        return serve(request, ruta, document_root=settings.MEDIA_ROOT)

    @staticmethod
    def _archivo_visible(usuario, ruta):
        obras = Obra.visibles_para(usuario).select_related(None).values("pk")
        return any(
            apps.get_model(modelo).objects.filter(**{campo: ruta, f"{relacion}__in": obras}).exists()
            for modelo, campo, relacion in _ARCHIVOS_DE_OBRA
        )
