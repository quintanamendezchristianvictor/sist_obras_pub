from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.db.models import Q, Sum

from core.validators import validar_documento, validar_pdf
from obras.models import Obra

ESTADO_REGISTRADA = "REGISTRADA"
ESTADO_APROBADA = "APROBADA"
ESTADO_OBSERVADA = "OBSERVADA"

ESTADO_VALORIZACION_CHOICES = [
    (ESTADO_REGISTRADA, "Registrada (pendiente de revisión)"),
    (ESTADO_APROBADA, "Aprobada por el supervisor"),
    (ESTADO_OBSERVADA, "Observada"),
]

TIPO_INFORME_RESIDENTE = "RESIDENTE"
TIPO_INFORME_SUPERVISOR = "SUPERVISOR"

TIPO_INFORME_CHOICES = [
    (TIPO_INFORME_RESIDENTE, "Informe del residente"),
    (TIPO_INFORME_SUPERVISOR, "Informe del supervisor"),
]


class Valorizacion(models.Model):
    """
    Valorización mensual de avance de obra (RF-16), con flujo de revisión y
    aprobación entre el residente y el supervisor/inspector (RF-19).
    """

    obra = models.ForeignKey(Obra, on_delete=models.CASCADE, related_name="valorizaciones")
    numero = models.PositiveIntegerField("N° de valorización")
    periodo = models.DateField("Periodo valorizado")
    monto = models.DecimalField("Monto valorizado (S/)", max_digits=14, decimal_places=2)
    fecha_presentacion = models.DateField("Fecha de presentación")

    estado = models.CharField("Estado", max_length=15, choices=ESTADO_VALORIZACION_CHOICES, default=ESTADO_REGISTRADA)
    observaciones_revision = models.TextField("Observaciones de la revisión", blank=True)

    archivo_pdf = models.FileField(
        "Documento de sustento (PDF)", upload_to="valorizaciones/%Y/%m/", null=True, blank=True, validators=[validar_pdf]
    )

    registrado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
        related_name="valorizaciones_registradas", verbose_name="Registrado por",
    )
    revisado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="valorizaciones_revisadas", verbose_name="Revisado por",
    )
    fecha_registro = models.DateTimeField("Fecha de registro", auto_now_add=True)
    fecha_revision = models.DateTimeField("Fecha de revisión", null=True, blank=True)

    class Meta:
        verbose_name = "Valorización"
        verbose_name_plural = "Valorizaciones"
        ordering = ["-periodo", "-numero"]
        unique_together = ("obra", "numero")
        indexes = [models.Index(fields=["obra", "estado"])]
        constraints = [
            models.CheckConstraint(condition=Q(monto__gt=0), name="valorizacion_monto_positivo"),
            models.UniqueConstraint(fields=["obra", "periodo"], name="valorizacion_unica_por_periodo"),
        ]

    def __str__(self):
        return f"Valorización N° {self.numero} - {self.obra.codigo}"

    @property
    def pendiente(self):
        return self.estado == ESTADO_REGISTRADA

    @property
    def observada(self):
        return self.estado == ESTADO_OBSERVADA


class InformeMensual(models.Model):
    """Informe mensual elaborado por el residente o el supervisor (RF-17)."""

    obra = models.ForeignKey(Obra, on_delete=models.CASCADE, related_name="informes")
    periodo = models.DateField("Periodo informado")
    tipo = models.CharField("Tipo de informe", max_length=15, choices=TIPO_INFORME_CHOICES)
    resumen = models.TextField("Resumen del informe")
    archivo = models.FileField("Archivo adjunto", upload_to="informes/%Y/%m/", null=True, blank=True, validators=[validar_documento])

    elaborado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="informes_elaborados",
    )
    fecha_elaboracion = models.DateTimeField("Fecha de elaboración", auto_now_add=True)

    class Meta:
        verbose_name = "Informe mensual"
        verbose_name_plural = "Informes mensuales"
        ordering = ["-periodo"]
        constraints = [models.UniqueConstraint(fields=["obra", "periodo", "tipo"], name="informe_unico_por_periodo_y_tipo")]

    def __str__(self):
        return f"Informe {self.get_tipo_display()} - {self.obra.codigo} ({self.periodo:%Y-%m})"

    def datos_periodo(self):
        """
        Datos registrados en el sistema para el periodo del informe (RF-17):
        el informe mensual se genera a partir de ellos, sin volver a digitarlos.
        """
        obra = self.obra
        inicio = self.periodo.replace(day=1)
        fin = (inicio + timedelta(days=32)).replace(day=1)
        en_el_mes = {"fecha_solicitud__gte": inicio, "fecha_solicitud__lt": fin}
        resueltas_en_el_mes = {"fecha_aprobacion__gte": inicio, "fecha_aprobacion__lt": fin}

        avance = obra.avances.filter(periodo=inicio).prefetch_related("evidencias").first()
        valorizaciones = obra.valorizaciones.filter(periodo__gte=inicio, periodo__lt=fin)
        acumulado = obra.valorizaciones.filter(periodo__lt=fin, estado=ESTADO_APROBADA).aggregate(t=Sum("monto"))["t"]
        return {
            "avance": avance,
            "evidencias": avance.evidencias.all() if avance else [],
            "programado": obra.calendario.filter(periodo=inicio).first(),
            "valorizaciones": valorizaciones,
            "valorizado_aprobado_acumulado": acumulado or Decimal("0"),
            "ampliaciones": obra.ampliaciones_plazo.filter(Q(**en_el_mes) | Q(**resueltas_en_el_mes)),
            "adicionales": obra.adicionales_deductivos.filter(Q(**en_el_mes) | Q(**resueltas_en_el_mes)),
            "presupuesto_vigente": obra.presupuesto_vigente,
            "plazo_vigente": obra.plazo_vigente_dias,
            "fecha_fin_vigente": obra.fecha_fin_vigente,
        }
