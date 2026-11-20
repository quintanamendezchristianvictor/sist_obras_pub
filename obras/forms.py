from datetime import timedelta

from django import forms
from django.forms import inlineformset_factory

from core.constants import ESTADO_CONCLUIDA, MODALIDAD_CONTRATA, ROL_RESIDENTE, ROL_SUPERVISOR, UNIDADES_ORGANICAS_SUGERIDAS
from usuarios.models import Usuario

from .models import ExpedienteTecnico, FichaInfobras, Obra, ParalizacionObra, PartidaExpediente

_WIDGET_CLASS = "form-control"
_SELECT_CLASS = "form-select"


class ObraForm(forms.ModelForm):
    """Registro y edición de la ficha técnica de la obra (RF-06, RF-08, RF-09)."""

    class Meta:
        model = Obra
        fields = [
            "codigo", "nombre", "descripcion",
            "direccion", "distrito", "provincia", "departamento",
            "modalidad_ejecucion", "meta_fisica", "unidad_medida",
            "plazo_ejecucion_dias", "fecha_inicio", "fecha_fin_programada",
            "presupuesto_asignado", "estado", "unidad_organica",
            "residente", "supervisor", "contratista", "contratista_ruc",
        ]
        widgets = {
            "codigo": forms.TextInput(attrs={"class": _WIDGET_CLASS}),
            "nombre": forms.TextInput(attrs={"class": _WIDGET_CLASS}),
            "descripcion": forms.Textarea(attrs={"class": _WIDGET_CLASS, "rows": 3}),
            "direccion": forms.TextInput(attrs={"class": _WIDGET_CLASS}),
            "distrito": forms.TextInput(attrs={"class": _WIDGET_CLASS}),
            "provincia": forms.TextInput(attrs={"class": _WIDGET_CLASS}),
            "departamento": forms.TextInput(attrs={"class": _WIDGET_CLASS}),
            "modalidad_ejecucion": forms.Select(attrs={"class": _SELECT_CLASS}),
            "meta_fisica": forms.TextInput(attrs={"class": _WIDGET_CLASS}),
            "unidad_medida": forms.TextInput(attrs={"class": _WIDGET_CLASS}),
            "plazo_ejecucion_dias": forms.NumberInput(attrs={"class": _WIDGET_CLASS}),
            "fecha_inicio": forms.DateInput(attrs={"class": _WIDGET_CLASS, "type": "date"}, format="%Y-%m-%d"),
            "fecha_fin_programada": forms.DateInput(attrs={"class": _WIDGET_CLASS, "type": "date"}, format="%Y-%m-%d"),
            "presupuesto_asignado": forms.NumberInput(attrs={"class": _WIDGET_CLASS, "step": "0.01"}),
            "estado": forms.Select(attrs={"class": _SELECT_CLASS}),
            "unidad_organica": forms.TextInput(attrs={"class": _WIDGET_CLASS, "list": "unidades-organicas"}),
            "residente": forms.Select(attrs={"class": _SELECT_CLASS}),
            "supervisor": forms.Select(attrs={"class": _SELECT_CLASS}),
            "contratista": forms.TextInput(attrs={"class": _WIDGET_CLASS}),
            "contratista_ruc": forms.TextInput(attrs={"class": _WIDGET_CLASS, "maxlength": 11, "inputmode": "numeric"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["residente"].queryset = Usuario.objects.filter(rol=ROL_RESIDENTE, is_active=True)
        self.fields["supervisor"].queryset = Usuario.objects.filter(rol=ROL_SUPERVISOR, is_active=True)
        self.fields["residente"].required = False
        self.fields["supervisor"].required = False

    @staticmethod
    def unidades_sugeridas():
        """Evita que una misma unidad se escriba de varias formas y parta el filtro (RF-10, RF-30)."""
        registradas = Obra.objects.order_by().values_list("unidad_organica", flat=True).distinct()
        return sorted(set(UNIDADES_ORGANICAS_SUGERIDAS) | set(registradas))

    def clean_estado(self):
        """Una obra solo puede declararse concluida con su avance físico al 100 % (RF-13)."""
        estado = self.cleaned_data["estado"]
        if estado == ESTADO_CONCLUIDA:
            avance = self.instance.avance_fisico_acumulado if self.instance.pk else 0.0
            if avance < 100:
                raise forms.ValidationError(
                    f"No se puede marcar la obra como concluida: su avance físico "
                    f"ejecutado es {avance:.1f}% (debe ser 100%)."
                )
        return estado

    def clean_presupuesto_asignado(self):
        presupuesto = self.cleaned_data["presupuesto_asignado"]
        if presupuesto <= 0:
            raise forms.ValidationError("El presupuesto asignado debe ser mayor que cero.")
        return presupuesto

    def clean_contratista_ruc(self):
        ruc = self.cleaned_data["contratista_ruc"].strip()
        if ruc and (len(ruc) != 11 or not ruc.isdigit()):
            raise forms.ValidationError("El RUC debe tener 11 dígitos.")
        return ruc

    def clean(self):
        datos = super().clean()
        inicio, fin, plazo = datos.get("fecha_inicio"), datos.get("fecha_fin_programada"), datos.get("plazo_ejecucion_dias")
        if inicio and fin and fin <= inicio:
            self.add_error("fecha_fin_programada", "La culminación programada debe ser posterior a la fecha de inicio.")
        elif inicio and fin and plazo and abs((fin - inicio).days - plazo) > 1:
            esperada = inicio + timedelta(days=plazo)
            self.add_error(
                "fecha_fin_programada",
                f"No coincide con el plazo de {plazo} días desde el inicio (debería ser {esperada:%d/%m/%Y}).",
            )
        if datos.get("modalidad_ejecucion") == MODALIDAD_CONTRATA and not datos.get("contratista"):
            self.add_error("contratista", "En la ejecución por contrata indique el contratista.")
        return datos


class ExpedienteTecnicoForm(forms.ModelForm):
    """Vinculación de la obra con su expediente técnico aprobado (RF-07)."""

    class Meta:
        model = ExpedienteTecnico
        fields = ["numero_expediente", "entidad_formuladora", "fecha_aprobacion", "monto_expediente", "archivo", "observaciones"]
        widgets = {
            "numero_expediente": forms.TextInput(attrs={"class": _WIDGET_CLASS}),
            "entidad_formuladora": forms.TextInput(attrs={"class": _WIDGET_CLASS}),
            "fecha_aprobacion": forms.DateInput(attrs={"class": _WIDGET_CLASS, "type": "date"}, format="%Y-%m-%d"),
            "monto_expediente": forms.NumberInput(attrs={"class": _WIDGET_CLASS, "step": "0.01"}),
            "archivo": forms.ClearableFileInput(attrs={"class": "form-control"}),
            "observaciones": forms.Textarea(attrs={"class": _WIDGET_CLASS, "rows": 3}),
        }


class PartidaExpedienteForm(forms.ModelForm):
    """Partida del presupuesto del expediente técnico con su metrado programado (RF-11)."""

    class Meta:
        model = PartidaExpediente
        fields = ["item", "descripcion", "unidad", "metrado", "precio_unitario"]
        widgets = {
            "item": forms.TextInput(attrs={"class": _WIDGET_CLASS + " form-control-sm", "placeholder": "01.01"}),
            "descripcion": forms.TextInput(attrs={"class": _WIDGET_CLASS + " form-control-sm"}),
            "unidad": forms.TextInput(attrs={"class": _WIDGET_CLASS + " form-control-sm", "placeholder": "m3"}),
            "metrado": forms.NumberInput(attrs={"class": _WIDGET_CLASS + " form-control-sm", "step": "0.01", "min": 0}),
            "precio_unitario": forms.NumberInput(attrs={"class": _WIDGET_CLASS + " form-control-sm", "step": "0.01", "min": 0}),
        }

    def clean(self):
        datos = super().clean()
        for campo in ("metrado", "precio_unitario"):
            valor = datos.get(campo)
            if valor is not None and valor <= 0:
                self.add_error(campo, "Debe ser mayor que cero.")
        return datos


class BasePartidasFormSet(forms.BaseInlineFormSet):
    def clean(self):
        super().clean()
        items = set()
        for form in self.forms:
            datos = getattr(form, "cleaned_data", None)
            if not datos:
                continue
            if datos.get("DELETE"):
                if form.instance.pk and form.instance.metrados_ejecutados.exists():
                    raise forms.ValidationError(
                        f"La partida {form.instance.item} ya tiene metrados ejecutados registrados y no puede eliminarse."
                    )
                continue
            item = datos.get("item")
            if item in items:
                raise forms.ValidationError(f"El ítem {item} está repetido.")
            items.add(item)


PartidasFormSet = inlineformset_factory(
    ExpedienteTecnico, PartidaExpediente, form=PartidaExpedienteForm, formset=BasePartidasFormSet,
    extra=3, can_delete=True,
)


class FichaInfobrasForm(forms.ModelForm):
    """Datos de la obra que exige INFOBRAS y no se registran en otros módulos (RF-28)."""

    SECCIONES = [
        ("Datos generales", ["naturaleza", "latitud", "longitud", "convenio"]),
        ("Ejecución", [
            "fecha_entrega_terreno", "contrato_numero", "contrato_fecha", "contrato_monto",
            "adelanto_directo", "adelanto_materiales", "controversias",
        ]),
        ("Cierre", [
            "recepcion_fecha", "recepcion_acta", "liquidacion_fecha", "liquidacion_monto",
            "liquidacion_resolucion", "transferencia_entidad", "transferencia_fecha",
        ]),
    ]

    class Meta:
        model = FichaInfobras
        fields = [
            "naturaleza", "latitud", "longitud", "convenio",
            "fecha_entrega_terreno", "contrato_numero", "contrato_fecha", "contrato_monto",
            "adelanto_directo", "adelanto_materiales", "controversias",
            "recepcion_fecha", "recepcion_acta", "liquidacion_fecha", "liquidacion_monto",
            "liquidacion_resolucion", "transferencia_entidad", "transferencia_fecha",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for campo in self.fields.values():
            widget = campo.widget
            if isinstance(widget, forms.DateInput):
                widget.input_type = "date"
                widget.format = "%Y-%m-%d"
            if isinstance(widget, forms.Textarea):
                widget.attrs["rows"] = 2
            widget.attrs["class"] = _SELECT_CLASS if isinstance(widget, forms.Select) else _WIDGET_CLASS

    def secciones(self):
        return [(titulo, [self[nombre] for nombre in nombres]) for titulo, nombres in self.SECCIONES]

    def clean(self):
        datos = super().clean()
        if bool(datos.get("latitud") is None) != bool(datos.get("longitud") is None):
            self.add_error("longitud", "Indique la latitud y la longitud juntas.")
        recepcion, liquidacion = datos.get("recepcion_fecha"), datos.get("liquidacion_fecha")
        inicio = self.instance.obra.fecha_inicio if self.instance.obra_id else None
        if recepcion and inicio and recepcion < inicio:
            self.add_error("recepcion_fecha", "La recepción no puede ser anterior al inicio de la obra.")
        if liquidacion and recepcion and liquidacion < recepcion:
            self.add_error("liquidacion_fecha", "La liquidación no puede ser anterior a la recepción.")
        return datos


class ParalizacionForm(forms.ModelForm):
    class Meta:
        model = ParalizacionObra
        fields = ["fecha_inicio", "fecha_fin", "motivo"]
        widgets = {
            "fecha_inicio": forms.DateInput(attrs={"class": _WIDGET_CLASS + " form-control-sm", "type": "date"}, format="%Y-%m-%d"),
            "fecha_fin": forms.DateInput(attrs={"class": _WIDGET_CLASS + " form-control-sm", "type": "date"}, format="%Y-%m-%d"),
            "motivo": forms.TextInput(attrs={"class": _WIDGET_CLASS + " form-control-sm"}),
        }

    def clean(self):
        datos = super().clean()
        inicio, fin = datos.get("fecha_inicio"), datos.get("fecha_fin")
        if inicio and fin and fin < inicio:
            self.add_error("fecha_fin", "El fin no puede ser anterior al inicio.")
        return datos


ParalizacionesFormSet = inlineformset_factory(Obra, ParalizacionObra, form=ParalizacionForm, extra=2, can_delete=True)
