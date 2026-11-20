from django import forms

from .models import Documento

_WIDGET_CLASS = "form-control"
_SELECT_CLASS = "form-select"


class DocumentoForm(forms.ModelForm):
    """Carga de documentos al acervo documentario de la obra (RF-24, RF-25)."""

    class Meta:
        model = Documento
        fields = ["tipo_documento", "nombre", "periodo", "descripcion", "archivo"]
        widgets = {
            "tipo_documento": forms.Select(attrs={"class": _SELECT_CLASS}),
            "nombre": forms.TextInput(attrs={"class": _WIDGET_CLASS}),
            "periodo": forms.DateInput(attrs={"class": _WIDGET_CLASS, "type": "date"}, format="%Y-%m-%d"),
            "descripcion": forms.Textarea(attrs={"class": _WIDGET_CLASS, "rows": 2}),
            "archivo": forms.ClearableFileInput(attrs={"class": "form-control"}),
        }
