from datetime import date
from decimal import Decimal

from django import forms
from django.db.models import Sum

from core.forms import FormularioDeObraMixin, NumeroCorrelativoMixin

from .models import (
    ESTADO_APROBADA,
    ESTADO_APROBADO,
    ESTADO_RECHAZADA,
    ESTADO_RECHAZADO,
    TIPO_DEDUCTIVO,
    AdicionalDeductivo,
    AmpliacionPlazo,
    CalendarioEjecucion,
)

_WIDGET_CLASS = "form-control"
_SELECT_CLASS = "form-select"


class CalendarioEjecucionForm(FormularioDeObraMixin, forms.ModelForm):
    """Registro del calendario de ejecución valorizado (RF-20)."""

    periodo = forms.DateField(
        label="Periodo programado",
        input_formats=["%Y-%m", "%Y-%m-%d", "%d/%m/%Y"],
        widget=forms.DateInput(attrs={"class": _WIDGET_CLASS, "type": "month", "placeholder": "AAAA-MM"}, format="%Y-%m"),
    )

    class Meta:
        model = CalendarioEjecucion
        fields = ["periodo", "meta_programada", "monto_programado", "avance_fisico_programado", "observaciones"]
        widgets = {
            "meta_programada": forms.TextInput(attrs={"class": _WIDGET_CLASS}),
            "monto_programado": forms.NumberInput(attrs={"class": _WIDGET_CLASS, "step": "0.01", "min": 0}),
            "avance_fisico_programado": forms.NumberInput(attrs={"class": _WIDGET_CLASS, "step": "0.01", "min": 0, "max": 100}),
            "observaciones": forms.TextInput(attrs={"class": _WIDGET_CLASS}),
        }

    def clean_periodo(self):
        periodo = self.cleaned_data["periodo"].replace(day=1)
        if periodo < self.obra.fecha_inicio.replace(day=1):
            raise forms.ValidationError("El periodo no puede ser anterior al mes de inicio de la obra.")
        if self.obra.calendario.filter(periodo=periodo).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("Ese periodo ya está registrado en el calendario.")
        return periodo

    def clean(self):
        datos = super().clean()
        otros = self.obra.calendario.exclude(pk=self.instance.pk).aggregate(
            fisico=Sum("avance_fisico_programado"), monto=Sum("monto_programado")
        )
        fisico = datos.get("avance_fisico_programado")
        monto = datos.get("monto_programado")
        if fisico is not None:
            total = (otros["fisico"] or Decimal("0")) + fisico
            if fisico < 0 or total > 100:
                self.add_error(
                    "avance_fisico_programado",
                    f"La suma del avance físico programado de todos los periodos sería {total}% (máximo 100%).",
                )
        if monto is not None:
            total = (otros["monto"] or Decimal("0")) + monto
            vigente = self.obra.presupuesto_vigente
            if monto < 0 or total > vigente:
                self.add_error(
                    "monto_programado",
                    f"La suma de los montos programados (S/ {total:,.2f}) superaría el presupuesto vigente (S/ {vigente:,.2f}).",
                )
        return datos


class AmpliacionPlazoForm(NumeroCorrelativoMixin, forms.ModelForm):
    """Registro de la solicitud de ampliación de plazo (RF-21). Se aprueba o rechaza después."""

    class Meta:
        model = AmpliacionPlazo
        fields = ["numero", "fecha_solicitud", "motivo", "dias_solicitados", "documento_sustento"]
        widgets = {
            "numero": forms.NumberInput(attrs={"class": _WIDGET_CLASS}),
            "fecha_solicitud": forms.DateInput(attrs={"class": _WIDGET_CLASS, "type": "date"}, format="%Y-%m-%d"),
            "motivo": forms.Textarea(attrs={"class": _WIDGET_CLASS, "rows": 3}),
            "dias_solicitados": forms.NumberInput(attrs={"class": _WIDGET_CLASS, "min": 1}),
            "documento_sustento": forms.ClearableFileInput(attrs={"class": "form-control"}),
        }

    def relacionados(self):
        return self.obra.ampliaciones_plazo.all()

    def clean_dias_solicitados(self):
        dias = self.cleaned_data["dias_solicitados"]
        if dias < 1:
            raise forms.ValidationError("Debe solicitar al menos un día.")
        return dias

    def clean_fecha_solicitud(self):
        fecha = self.cleaned_data["fecha_solicitud"]
        if fecha > date.today():
            raise forms.ValidationError("La fecha de solicitud no puede ser futura.")
        return fecha


class AdicionalDeductivoForm(NumeroCorrelativoMixin, forms.ModelForm):
    """Registro de la solicitud de adicional o deductivo de obra (RF-22). Se aprueba o rechaza después."""

    class Meta:
        model = AdicionalDeductivo
        fields = ["tipo", "numero", "monto", "sustento", "fecha_solicitud", "documento_sustento"]
        widgets = {
            "tipo": forms.Select(attrs={"class": _SELECT_CLASS}),
            "numero": forms.NumberInput(attrs={"class": _WIDGET_CLASS}),
            "monto": forms.NumberInput(attrs={"class": _WIDGET_CLASS, "step": "0.01", "min": 0}),
            "sustento": forms.Textarea(attrs={"class": _WIDGET_CLASS, "rows": 3}),
            "fecha_solicitud": forms.DateInput(attrs={"class": _WIDGET_CLASS, "type": "date"}, format="%Y-%m-%d"),
            "documento_sustento": forms.ClearableFileInput(attrs={"class": "form-control"}),
        }

    def relacionados(self):
        return self.obra.adicionales_deductivos.all()

    def clean_numero(self):
        # El correlativo es independiente para adicionales y para deductivos
        numero = self.cleaned_data["numero"]
        tipo = self.data.get(self.add_prefix("tipo"))
        if self.relacionados().filter(numero=numero, tipo=tipo).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError(f"Ya existe un registro de ese tipo con el N° {numero} en esta obra.")
        return numero

    def clean_monto(self):
        monto = self.cleaned_data["monto"]
        if monto <= 0:
            raise forms.ValidationError("El monto debe ser mayor que cero.")
        return monto

    def clean_fecha_solicitud(self):
        fecha = self.cleaned_data["fecha_solicitud"]
        if fecha > date.today():
            raise forms.ValidationError("La fecha de solicitud no puede ser futura.")
        return fecha


class ResolucionMixin:
    """
    Aprobación o rechazo de una solicitud (RF-21, RF-22). Al aprobarse,
    el plazo y/o el presupuesto vigente de la obra se recalculan
    automáticamente (RF-23), porque se derivan siempre de las solicitudes
    aprobadas.
    """

    estado_aprobado = None
    estados_resolucion = ()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["estado"].choices = [c for c in self.fields["estado"].choices if c[0] in self.estados_resolucion]
        self.fields["fecha_aprobacion"].required = True
        self.fields["resolucion"].required = True
        self.initial.setdefault("fecha_aprobacion", date.today())

    def clean_fecha_aprobacion(self):
        fecha = self.cleaned_data["fecha_aprobacion"]
        if fecha < self.instance.fecha_solicitud:
            raise forms.ValidationError("La fecha de resolución no puede ser anterior a la fecha de solicitud.")
        if fecha > date.today():
            raise forms.ValidationError("La fecha de resolución no puede ser futura.")
        return fecha


class ResolverAmpliacionForm(ResolucionMixin, forms.ModelForm):
    estado_aprobado = ESTADO_APROBADA
    estados_resolucion = (ESTADO_APROBADA, ESTADO_RECHAZADA)

    class Meta:
        model = AmpliacionPlazo
        fields = ["estado", "dias_otorgados", "fecha_aprobacion", "resolucion"]
        widgets = {
            "estado": forms.Select(attrs={"class": _SELECT_CLASS}),
            "dias_otorgados": forms.NumberInput(attrs={"class": _WIDGET_CLASS, "min": 0}),
            "fecha_aprobacion": forms.DateInput(attrs={"class": _WIDGET_CLASS, "type": "date"}, format="%Y-%m-%d"),
            "resolucion": forms.TextInput(attrs={"class": _WIDGET_CLASS, "placeholder": "Ej.: R.A. N° 045-2026-MDSR"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.initial["dias_otorgados"] = self.instance.dias_solicitados

    def clean(self):
        datos = super().clean()
        dias = datos.get("dias_otorgados")
        if datos.get("estado") == ESTADO_APROBADA and dias is not None:
            if dias < 1:
                self.add_error("dias_otorgados", "Una ampliación aprobada debe otorgar al menos un día.")
            elif dias > self.instance.dias_solicitados:
                self.add_error("dias_otorgados", f"No puede otorgar más días que los solicitados ({self.instance.dias_solicitados}).")
        elif datos.get("estado") == ESTADO_RECHAZADA:
            datos["dias_otorgados"] = 0
            self.instance.dias_otorgados = 0
        return datos


class ResolverAdicionalForm(ResolucionMixin, forms.ModelForm):
    estado_aprobado = ESTADO_APROBADO
    estados_resolucion = (ESTADO_APROBADO, ESTADO_RECHAZADO)

    class Meta:
        model = AdicionalDeductivo
        fields = ["estado", "fecha_aprobacion", "resolucion"]
        widgets = {
            "estado": forms.Select(attrs={"class": _SELECT_CLASS}),
            "fecha_aprobacion": forms.DateInput(attrs={"class": _WIDGET_CLASS, "type": "date"}, format="%Y-%m-%d"),
            "resolucion": forms.TextInput(attrs={"class": _WIDGET_CLASS, "placeholder": "Ej.: R.A. N° 045-2026-MDSR"}),
        }

    def clean(self):
        datos = super().clean()
        item = self.instance
        if datos.get("estado") == ESTADO_APROBADO and item.tipo == TIPO_DEDUCTIVO:
            vigente = item.obra.presupuesto_vigente
            if item.monto >= vigente:
                raise forms.ValidationError(
                    f"El deductivo (S/ {item.monto:,.2f}) no puede igualar ni superar el presupuesto vigente (S/ {vigente:,.2f})."
                )
        return datos
