from datetime import date
from decimal import Decimal

from django import forms
from django.db import transaction

from .models import AvanceObra, EvidenciaAvance, MetradoEjecutado

_WIDGET_CLASS = "form-control"
_CIEN = Decimal("100")
_DOS_DECIMALES = Decimal("0.01")


def _porcentaje(parte, total):
    if not total:
        return Decimal("0")
    return min(Decimal(parte) * _CIEN / Decimal(total), _CIEN).quantize(_DOS_DECIMALES)


class AvanceObraForm(forms.ModelForm):
    """
    Registro del avance físico y financiero por periodo (RF-11, RF-12, RF-15).

    El residente solo ingresa lo ejecutado; el sistema calcula el resto
    (RF-13, RF-14):
    - Avance físico ejecutado: a partir de los metrados ejecutados de las
      partidas del expediente técnico (RF-11) o, si la obra no tiene
      partidas registradas, el porcentaje que digita el residente.
    - Avance financiero ejecutado: monto devengado / presupuesto vigente.
    - Avances programados: acumulado del calendario de ejecución valorizado
      hasta el periodo (RF-20). Solo si la obra aún no tiene calendario se
      piden de forma manual.
    """

    periodo = forms.DateField(
        label="Periodo (mes de reporte)",
        input_formats=["%Y-%m", "%Y-%m-%d", "%d/%m/%Y"],
        widget=forms.DateInput(
            attrs={"class": _WIDGET_CLASS, "type": "month", "placeholder": "AAAA-MM"}, format="%Y-%m"
        ),
    )

    class Meta:
        model = AvanceObra
        fields = [
            "periodo", "avance_fisico_ejecutado_acum", "monto_devengado_acum",
            "avance_fisico_programado_acum", "avance_financiero_programado_acum", "observaciones",
        ]
        widgets = {
            "avance_fisico_ejecutado_acum": forms.NumberInput(attrs={"class": _WIDGET_CLASS, "step": "0.01", "min": 0, "max": 100}),
            "monto_devengado_acum": forms.NumberInput(attrs={"class": _WIDGET_CLASS, "step": "0.01", "min": 0}),
            "avance_fisico_programado_acum": forms.NumberInput(attrs={"class": _WIDGET_CLASS, "step": "0.01", "min": 0, "max": 100}),
            "avance_financiero_programado_acum": forms.NumberInput(attrs={"class": _WIDGET_CLASS, "step": "0.01", "min": 0, "max": 100}),
            "observaciones": forms.Textarea(attrs={"class": _WIDGET_CLASS, "rows": 3}),
        }

    def __init__(self, *args, obra, **kwargs):
        super().__init__(*args, **kwargs)
        self.obra = obra
        if not self.instance.pk:
            self.instance.obra = obra
        self.tiene_calendario = obra.calendario.exists()
        try:
            self.partidas = list(obra.expediente_tecnico.partidas.all())
        except obra.__class__.expediente_tecnico.RelatedObjectDoesNotExist:
            self.partidas = []

        self.fields["monto_devengado_acum"].required = True
        self.fields["avance_fisico_programado_acum"].required = False
        self.fields["avance_financiero_programado_acum"].required = False
        if self.tiene_calendario:
            del self.fields["avance_fisico_programado_acum"]
            del self.fields["avance_financiero_programado_acum"]

        # RF-11: un campo de metrado ejecutado acumulado por cada partida del expediente
        if self.partidas:
            del self.fields["avance_fisico_ejecutado_acum"]
            previos = self._metrados_previos()
            for partida in self.partidas:
                self.fields[f"metrado_{partida.pk}"] = forms.DecimalField(
                    label=f"{partida.item} {partida.descripcion}",
                    min_value=0, max_digits=14, decimal_places=2,
                    help_text=f"Programado: {partida.metrado} {partida.unidad}",
                    initial=previos.get(partida.pk, Decimal("0")),
                    widget=forms.NumberInput(attrs={"class": _WIDGET_CLASS, "step": "0.01", "min": 0}),
                )

    def _metrados_previos(self):
        """Metrados del avance que se edita o, si es nuevo, del último registrado."""
        avance = self.instance if self.instance.pk else self.obra.avances.order_by("-periodo").first()
        if not avance:
            return {}
        return {m.partida_id: m.metrado_acumulado for m in avance.metrados.all()}

    def campos_metrado(self):
        return [self[f"metrado_{p.pk}"] for p in self.partidas]

    def clean_periodo(self):
        periodo = self.cleaned_data["periodo"].replace(day=1)
        if periodo < self.obra.fecha_inicio.replace(day=1):
            raise forms.ValidationError("El periodo no puede ser anterior al mes de inicio de la obra.")
        if periodo > date.today().replace(day=1):
            raise forms.ValidationError("No se puede registrar el avance de un mes que aún no ha transcurrido.")
        repetido = self.obra.avances.filter(periodo=periodo).exclude(pk=self.instance.pk)
        if repetido.exists():
            raise forms.ValidationError("Ya existe un registro de avance para ese periodo.")
        return periodo

    def clean(self):
        datos = super().clean()
        periodo = datos.get("periodo")
        monto = datos.get("monto_devengado_acum")
        if periodo is None or monto is None:
            return datos

        otros = self.obra.avances.exclude(pk=self.instance.pk)
        anterior = otros.filter(periodo__lt=periodo).order_by("-periodo").first()
        siguiente = otros.filter(periodo__gt=periodo).order_by("periodo").first()

        # Avance físico ejecutado (RF-11, RF-13)
        if self.partidas:
            fisico = self._fisico_desde_metrados(datos, anterior)
        else:
            fisico = datos.get("avance_fisico_ejecutado_acum")
            if fisico is not None and not (0 <= fisico <= _CIEN):
                self.add_error("avance_fisico_ejecutado_acum", "El porcentaje debe estar entre 0 y 100.")
                fisico = None
        if fisico is not None:
            self._validar_secuencia("avance físico ejecutado", fisico, anterior, siguiente,
                                    "avance_fisico_ejecutado_acum", "%")

        # Avance financiero ejecutado (RF-12, RF-13)
        presupuesto = self.obra.presupuesto_vigente
        if monto < 0 or monto > presupuesto:
            self.add_error(
                "monto_devengado_acum",
                f"El monto devengado acumulado debe estar entre S/ 0.00 y el presupuesto vigente (S/ {presupuesto:,.2f}).",
            )
        else:
            self._validar_secuencia("monto devengado acumulado", monto, anterior, siguiente,
                                    "monto_devengado_acum", " soles")

        # Avance programado (RF-14, RF-20)
        if self.tiene_calendario:
            fisico_prog, financiero_prog = self.obra.programado_acumulado_al(periodo)
        else:
            fisico_prog = datos.get("avance_fisico_programado_acum")
            financiero_prog = datos.get("avance_financiero_programado_acum")
            for campo, valor in (("avance_fisico_programado_acum", fisico_prog),
                                 ("avance_financiero_programado_acum", financiero_prog)):
                if valor is None:
                    self.add_error(campo, "La obra no tiene calendario de ejecución: ingrese el valor programado.")
                elif not (0 <= valor <= _CIEN):
                    self.add_error(campo, "El porcentaje debe estar entre 0 y 100.")

        if not self.errors:
            self.instance.avance_fisico_ejecutado_acum = fisico
            self.instance.avance_financiero_ejecutado_acum = _porcentaje(monto, presupuesto)
            self.instance.avance_fisico_programado_acum = fisico_prog
            self.instance.avance_financiero_programado_acum = financiero_prog
        return datos

    def _fisico_desde_metrados(self, datos, anterior):
        previos = {m.partida_id: m.metrado_acumulado for m in anterior.metrados.all()} if anterior else {}
        ejecutado = total = Decimal("0")
        for partida in self.partidas:
            campo = f"metrado_{partida.pk}"
            metrado = datos.get(campo)
            if metrado is None:
                continue
            if metrado > partida.metrado:
                self.add_error(campo, f"Supera el metrado programado ({partida.metrado} {partida.unidad}).")
            elif metrado < previos.get(partida.pk, 0):
                self.add_error(campo, f"Es menor al acumulado del periodo anterior ({previos[partida.pk]}).")
            ejecutado += min(metrado, partida.metrado) * partida.precio_unitario
            total += partida.parcial
        return _porcentaje(ejecutado, total)

    def _validar_secuencia(self, nombre, valor, anterior, siguiente, campo, unidad):
        """Un valor acumulado no puede retroceder respecto del periodo anterior ni superar al siguiente."""
        # Con partidas, el % físico no es un campo del formulario: el error se muestra en general
        destino = None if campo not in self.fields else campo
        if anterior:
            previo = getattr(anterior, campo) or Decimal("0")
            if valor < previo:
                self.add_error(destino, f"El {nombre} no puede ser menor al del periodo anterior ({previo}{unidad}).")
        if siguiente:
            posterior = getattr(siguiente, campo) or Decimal("0")
            if valor > posterior:
                self.add_error(destino, f"El {nombre} no puede superar al del periodo posterior ({posterior}{unidad}).")

    def save(self, commit=True):
        # El avance y sus metrados se guardan juntos o no se guarda nada (RNF-19)
        with transaction.atomic():
            avance = super().save(commit=commit)
            if commit and self.partidas:
                for partida in self.partidas:
                    MetradoEjecutado.objects.update_or_create(
                        avance=avance, partida=partida,
                        defaults={"metrado_acumulado": self.cleaned_data[f"metrado_{partida.pk}"]},
                    )
        return avance


class EvidenciaAvanceForm(forms.ModelForm):
    """Carga de evidencia fotográfica del avance (RF-15), a modo de cuaderno de obra digital."""

    class Meta:
        model = EvidenciaAvance
        fields = ["imagen", "descripcion"]
        widgets = {
            "imagen": forms.ClearableFileInput(attrs={"class": "form-control", "accept": "image/*"}),
            "descripcion": forms.TextInput(attrs={"class": _WIDGET_CLASS, "placeholder": "Descripción breve de la evidencia"}),
        }
