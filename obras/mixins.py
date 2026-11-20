from functools import cached_property

from django.shortcuts import get_object_or_404

from .models import Obra


class ObraVisibleMixin:
    """
    Para las vistas anidadas bajo una obra (/<modulo>/obra/<obra_pk>/...):
    expone `self.obra` buscándola solo entre las obras visibles para el rol del
    usuario (RF-04, RNF-17). Así un residente o supervisor no puede consultar ni
    registrar información de una obra ajena escribiendo la URL a mano (404).

    Debe ir después de RolRequeridoMixin, para que primero se valide la sesión.
    """

    @cached_property
    def obra(self):
        return get_object_or_404(Obra.visibles_para(self.request.user), pk=self.kwargs["obra_pk"])

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["obra"] = self.obra
        return ctx
