from datetime import date
from decimal import Decimal

from django import forms
from django.db.models import Sum

from core.forms import NumeroCorrelativoMixin

from .models import ESTADO_APROBADA, ESTADO_OBSERVADA, InformeMensual, Valorizacion

_WIDGET_CLASS = "form-control"
_SELECT_CLASS = "form-select"


def _campo_periodo(etiqueta):
    return forms.DateField(
        label=etiqueta,
        input_formats=["%Y-%m", "%Y-%m-%d", "%d/%m/%Y"],
        widget=forms.DateInput(attrs={"class": _WIDGET_CLASS, "type": "month", "placeholder": "AAAA-MM"}, format="%Y-%m"),
    )


class ValorizacionForm(NumeroCorrelativoMixin, forms.ModelForm):
    """Registro (o subsanación, si fue observada) de una valorización mensual (RF-16, RF-19)."""

    periodo = _campo_periodo("Periodo valorizado")

    class Meta:
        model = Valorizacion
        fields = ["numero", "periodo", "monto", "fecha_presentacion", "archivo_pdf"]
        widgets = {
            "numero": forms.NumberInput(attrs={"class": _WIDGET_CLASS}),
            "monto": forms.NumberInput(attrs={"class": _WIDGET_CLASS, "step": "0.01", "min": 0}),
            "fecha_presentacion": forms.DateInput(attrs={"class": _WIDGET_CLASS, "type": "date"}, format="%Y-%m-%d"),
            "archivo_pdf": forms.ClearableFileInput(attrs={"class": "form-control"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance.pk:
            self.initial.setdefault("fecha_presentacion", date.today())

    def relacionados(self):
        return self.obra.valorizaciones.all()

    def clean_periodo(self):
        periodo = self.cleaned_data["periodo"].replace(day=1)
        if periodo < self.obra.fecha_inicio.replace(day=1):
            raise forms.ValidationError("El periodo no puede ser anterior al mes de inicio de la obra.")
        if periodo > date.today().replace(day=1):
            raise forms.ValidationError("No se puede valorizar un mes que aún no ha transcurrido.")
        if self.relacionados().filter(periodo=periodo).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("Ya existe una valorización registrada para ese periodo.")
        return periodo

    def clean(self):
        datos = super().clean()
        periodo, monto, presentacion = datos.get("periodo"), datos.get("monto"), datos.get("fecha_presentacion")
        if monto is not None:
            if monto <= 0:
                self.add_error("monto", "El monto valorizado debe ser mayor que cero.")
            else:
                previo = self.relacionados().exclude(pk=self.instance.pk).aggregate(t=Sum("monto"))["t"] or Decimal("0")
                vigente = self.obra.presupuesto_vigente
                if previo + monto > vigente:
                    self.add_error(
                        "monto",
                        f"Con este monto el total valorizado (S/ {previo + monto:,.2f}) superaría el presupuesto vigente (S/ {vigente:,.2f}).",
                    )
        if periodo and presentacion and presentacion < periodo:
            self.add_error("fecha_presentacion", "La fecha de presentación no puede ser anterior al periodo valorizado.")
        return datos


class ValorizacionRevisionForm(forms.ModelForm):
    """Revisión de una valorización por el supervisor: aprobar u observar (RF-19)."""

    class Meta:
        model = Valorizacion
        fields = ["estado", "observaciones_revision"]
        widgets = {
            "estado": forms.Select(attrs={"class": _SELECT_CLASS}),
            "observaciones_revision": forms.Textarea(attrs={"class": _WIDGET_CLASS, "rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["estado"].label = "Resultado de la revisión"
        self.fields["estado"].choices = [
            (ESTADO_APROBADA, "Aprobar la valorización"),
            (ESTADO_OBSERVADA, "Observar (devolver al residente para su corrección)"),
        ]
        self.initial["estado"] = ESTADO_APROBADA

    def clean(self):
        datos = super().clean()
        if datos.get("estado") == ESTADO_OBSERVADA and not datos.get("observaciones_revision", "").strip():
            self.add_error("observaciones_revision", "Indique las observaciones que el residente debe subsanar.")
        return datos


class InformeMensualForm(forms.ModelForm):
    """
    Elaboración del informe mensual del residente o supervisor (RF-17). Los
    datos del periodo (avance, valorizaciones, modificaciones) se incorporan
    automáticamente; aquí solo se redacta la evaluación del profesional.
    """

    periodo = _campo_periodo("Periodo informado")

    class Meta:
        model = InformeMensual
        fields = ["periodo", "tipo", "resumen", "archivo"]
        labels = {"resumen": "Evaluación y conclusiones del periodo"}
        widgets = {
            "tipo": forms.Select(attrs={"class": _SELECT_CLASS}),
            "resumen": forms.Textarea(attrs={"class": _WIDGET_CLASS, "rows": 5}),
            "archivo": forms.ClearableFileInput(attrs={"class": "form-control"}),
        }

    def __init__(self, *args, obra, tipo=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.obra = obra
        # El tipo de informe se deduce del rol de quien lo elabora
        if tipo:
            del self.fields["tipo"]
            self.instance.tipo = tipo

    def clean_periodo(self):
        periodo = self.cleaned_data["periodo"].replace(day=1)
        if periodo < self.obra.fecha_inicio.replace(day=1):
            raise forms.ValidationError("El periodo no puede ser anterior al mes de inicio de la obra.")
        if periodo > date.today().replace(day=1):
            raise forms.ValidationError("No se puede informar un mes que aún no ha transcurrido.")
        return periodo

    def clean(self):
        datos = super().clean()
        tipo = datos.get("tipo", self.instance.tipo)
        periodo = datos.get("periodo")
        if periodo and tipo and self.obra.informes.filter(periodo=periodo, tipo=tipo).exclude(pk=self.instance.pk).exists():
            self.add_error("periodo", "Ya existe un informe de este tipo para ese periodo.")
        return datos
