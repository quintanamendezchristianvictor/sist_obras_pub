from django.conf import settings
from django.db import models
from django.db.models import Q

from core.validators import validar_documento
from obras.models import Obra

ESTADO_SOLICITADA = "SOLICITADA"
ESTADO_APROBADA = "APROBADA"
ESTADO_RECHAZADA = "RECHAZADA"

ESTADO_AMPLIACION_CHOICES = [
    (ESTADO_SOLICITADA, "Solicitada"),
    (ESTADO_APROBADA, "Aprobada"),
    (ESTADO_RECHAZADA, "Rechazada"),
]

TIPO_ADICIONAL = "ADICIONAL"
TIPO_DEDUCTIVO = "DEDUCTIVO"

TIPO_ADICIONAL_DEDUCTIVO_CHOICES = [
    (TIPO_ADICIONAL, "Adicional de obra"),
    (TIPO_DEDUCTIVO, "Deductivo de obra"),
]

ESTADO_SOLICITADO = "SOLICITADO"
ESTADO_APROBADO = "APROBADO"
ESTADO_RECHAZADO = "RECHAZADO"

ESTADO_ADICIONAL_DEDUCTIVO_CHOICES = [
    (ESTADO_SOLICITADO, "Solicitado"),
    (ESTADO_APROBADO, "Aprobado"),
    (ESTADO_RECHAZADO, "Rechazado"),
]


class CalendarioEjecucion(models.Model):
    """Calendario de ejecución valorizado de la obra, por periodo (RF-20)."""

    obra = models.ForeignKey(Obra, on_delete=models.CASCADE, related_name="calendario")
    periodo = models.DateField("Periodo programado")
    meta_programada = models.CharField("Meta física programada del periodo", max_length=255, blank=True)
    monto_programado = models.DecimalField("Monto programado (S/)", max_digits=14, decimal_places=2)
    avance_fisico_programado = models.DecimalField(
        "Avance físico programado del periodo (%)", max_digits=5, decimal_places=2
    )
    observaciones = models.CharField("Observaciones", max_length=255, blank=True)

    class Meta:
        verbose_name = "Calendario de ejecución"
        verbose_name_plural = "Calendario de ejecución"
        ordering = ["periodo"]
        unique_together = ("obra", "periodo")
        constraints = [
            models.CheckConstraint(condition=Q(monto_programado__gte=0), name="calendario_monto_no_negativo"),
            models.CheckConstraint(condition=Q(avance_fisico_programado__gte=0, avance_fisico_programado__lte=100), name="calendario_fisico_0_100"),
        ]

    def __str__(self):
        return f"Calendario {self.obra.codigo} - {self.periodo:%Y-%m}"


class AmpliacionPlazo(models.Model):
    """Ampliación de plazo de ejecución de obra (RF-21, RF-23)."""

    obra = models.ForeignKey(Obra, on_delete=models.CASCADE, related_name="ampliaciones_plazo")
    numero = models.PositiveIntegerField("N° de ampliación")
    fecha_solicitud = models.DateField("Fecha de solicitud")
    motivo = models.TextField("Motivo")
    dias_solicitados = models.PositiveIntegerField("Días solicitados", default=0)
    dias_otorgados = models.PositiveIntegerField(
        "Días otorgados", default=0, help_text="Se fija al aprobar la solicitud; solo estos días amplían el plazo (RF-23)."
    )
    estado = models.CharField("Estado", max_length=12, choices=ESTADO_AMPLIACION_CHOICES, default=ESTADO_SOLICITADA)
    fecha_aprobacion = models.DateField("Fecha de resolución", null=True, blank=True)
    resolucion = models.CharField("N° de resolución", max_length=100, blank=True)
    documento_sustento = models.FileField("Documento de sustento", upload_to="ampliaciones/%Y/%m/", null=True, blank=True, validators=[validar_documento])

    registrado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="ampliaciones_registradas",
    )
    fecha_registro = models.DateTimeField("Fecha de registro", auto_now_add=True)

    class Meta:
        verbose_name = "Ampliación de plazo"
        verbose_name_plural = "Ampliaciones de plazo"
        ordering = ["-fecha_solicitud"]
        unique_together = ("obra", "numero")
        indexes = [models.Index(fields=["obra", "estado"])]

    def __str__(self):
        return f"Ampliación N° {self.numero} - {self.obra.codigo} ({self.dias_solicitados} días solicitados)"

    @property
    def pendiente(self):
        return self.estado == ESTADO_SOLICITADA


class AdicionalDeductivo(models.Model):
    """Adicionales y deductivos de obra (RF-22, RF-23)."""

    obra = models.ForeignKey(Obra, on_delete=models.CASCADE, related_name="adicionales_deductivos")
    tipo = models.CharField("Tipo", max_length=10, choices=TIPO_ADICIONAL_DEDUCTIVO_CHOICES)
    numero = models.PositiveIntegerField("N°")
    monto = models.DecimalField("Monto (S/)", max_digits=14, decimal_places=2)
    sustento = models.TextField("Sustento técnico")
    estado = models.CharField(
        "Estado", max_length=12, choices=ESTADO_ADICIONAL_DEDUCTIVO_CHOICES, default=ESTADO_SOLICITADO
    )
    fecha_solicitud = models.DateField("Fecha de solicitud")
    fecha_aprobacion = models.DateField("Fecha de resolución", null=True, blank=True)
    resolucion = models.CharField("N° de resolución", max_length=100, blank=True)
    documento_sustento = models.FileField("Documento de sustento", upload_to="adicionales/%Y/%m/", null=True, blank=True, validators=[validar_documento])

    registrado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="adicionales_registrados",
    )
    fecha_registro = models.DateTimeField("Fecha de registro", auto_now_add=True)

    class Meta:
        verbose_name = "Adicional / Deductivo"
        verbose_name_plural = "Adicionales y deductivos"
        ordering = ["-fecha_solicitud"]
        unique_together = ("obra", "tipo", "numero")
        indexes = [models.Index(fields=["obra", "estado"])]
        constraints = [models.CheckConstraint(condition=Q(monto__gt=0), name="adicional_monto_positivo")]

    def __str__(self):
        return f"{self.get_tipo_display()} N° {self.numero} - {self.obra.codigo}"

    @property
    def pendiente(self):
        return self.estado == ESTADO_SOLICITADO
