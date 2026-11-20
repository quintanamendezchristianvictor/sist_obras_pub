"""
Comportamiento compartido por los formularios de los módulos que dependen de
una obra (avances, valorizaciones, calendario, etc.).
"""

from django import forms


class FormularioDeObraMixin:
    """Recibe la obra a la que pertenece el registro, para las validaciones que dependen de ella."""

    def __init__(self, *args, obra, **kwargs):
        super().__init__(*args, **kwargs)
        self.obra = obra


class NumeroCorrelativoMixin(FormularioDeObraMixin):
    """
    Propone el siguiente número correlativo (RNF-14: menos pasos para el
    usuario) y valida que no se repita dentro de la obra.
    """

    def relacionados(self):
        raise NotImplementedError

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance.pk:
            ultimo = self.relacionados().order_by("-numero").first()
            self.initial.setdefault("numero", (ultimo.numero + 1) if ultimo else 1)

    def clean_numero(self):
        numero = self.cleaned_data["numero"]
        if self.relacionados().filter(numero=numero).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError(f"Ya existe un registro con el N° {numero} en esta obra.")
        return numero
