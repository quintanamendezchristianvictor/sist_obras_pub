from django.conf import settings
from django.db import models
from django.db.models import OuterRef, Q, Subquery

from core.constants import SEMAFORO_CHOICES
from core.utils import calcular_semaforo, comprimir_imagen
from core.validators import validar_imagen
from obras.models import Obra, PartidaExpediente


def ultimos_avances(obras, corte=None):
    """
    Último avance de cada obra, hasta el periodo de corte si se indica, en una
    sola consulta (RNF-04). Devuelve un diccionario {obra_id: avance}.
    """
    previos = AvanceObra.objects.filter(obra=OuterRef("obra"))
    if corte:
        previos = previos.filter(periodo__lte=corte)
    ultimo = previos.order_by("-periodo").values("pk")[:1]
    avances = AvanceObra.objects.filter(obra__in=[o.pk for o in obras], pk=Subquery(ultimo))
    return {avance.obra_id: avance for avance in avances}


def asignar_ultimos_avances(obras, corte=None):
    """Deja el último avance en cada obra para que sus indicadores no lo vuelvan a consultar."""
    ultimos = ultimos_avances(obras, corte)
    for obra in obras:
        obra._ultimo_avance = ultimos.get(obra.pk)
    return ultimos


class AvanceObra(models.Model):
    """
    Registro periódico (mensual) del avance físico y financiero de una obra,
    a modo de cuaderno de obra digital (RF-11 a RF-14).

    Los porcentajes se registran de forma acumulada (respecto del total de la
    obra), tal como se reporta habitualmente en los informes de valorización
    y en INFOBRAS.
    """

    obra = models.ForeignKey(Obra, on_delete=models.CASCADE, related_name="avances", verbose_name="Obra")
    periodo = models.DateField("Periodo (mes de reporte)", help_text="Use el primer día del mes correspondiente.")

    avance_fisico_programado_acum = models.DecimalField(
        "Avance físico programado acumulado (%)", max_digits=5, decimal_places=2
    )
    avance_fisico_ejecutado_acum = models.DecimalField(
        "Avance físico ejecutado acumulado (%)", max_digits=5, decimal_places=2
    )
    avance_financiero_programado_acum = models.DecimalField(
        "Avance financiero programado acumulado (%)", max_digits=5, decimal_places=2
    )
    avance_financiero_ejecutado_acum = models.DecimalField(
        "Avance financiero ejecutado acumulado (%)", max_digits=5, decimal_places=2
    )
    monto_devengado_acum = models.DecimalField(
        "Monto devengado acumulado (S/)", max_digits=14, decimal_places=2, null=True, blank=True
    )

    observaciones = models.TextField("Observaciones / incidencias", blank=True)
    registrado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="avances_registrados",
        verbose_name="Registrado por",
    )
    fecha_registro = models.DateTimeField("Fecha de registro", auto_now_add=True)

    class Meta:
        verbose_name = "Avance de obra"
        verbose_name_plural = "Avances de obra"
        ordering = ["-periodo"]
        unique_together = ("obra", "periodo")
        constraints = [
            models.CheckConstraint(
                condition=Q(**{f"{campo}__gte": 0, f"{campo}__lte": 100}), name=f"avance_{campo}_0_100",
            )
            for campo in (
                "avance_fisico_programado_acum", "avance_fisico_ejecutado_acum",
                "avance_financiero_programado_acum", "avance_financiero_ejecutado_acum",
            )
        ]

    def __str__(self):
        return f"Avance {self.obra.codigo} - {self.periodo:%Y-%m}"

    @property
    def desviacion_fisica(self):
        return float(self.avance_fisico_programado_acum) - float(self.avance_fisico_ejecutado_acum)

    @property
    def desviacion_financiera(self):
        return float(self.avance_financiero_programado_acum) - float(self.avance_financiero_ejecutado_acum)

    @property
    def estado_semaforo(self):
        from core.models import Configuracion

        config = Configuracion.actual()
        codigo, desviacion = calcular_semaforo(
            self.avance_fisico_programado_acum,
            self.avance_fisico_ejecutado_acum,
            config.umbral_riesgo,
            config.umbral_atraso,
        )
        return codigo

    def get_estado_semaforo_display(self):
        return dict(SEMAFORO_CHOICES).get(self.estado_semaforo, "-")


class MetradoEjecutado(models.Model):
    """
    Metrado ejecutado acumulado de una partida del expediente técnico al
    cierre del periodo de un avance (RF-11).
    """

    avance = models.ForeignKey(AvanceObra, on_delete=models.CASCADE, related_name="metrados")
    partida = models.ForeignKey(PartidaExpediente, on_delete=models.PROTECT, related_name="metrados_ejecutados")
    metrado_acumulado = models.DecimalField("Metrado ejecutado acumulado", max_digits=14, decimal_places=2)

    class Meta:
        verbose_name = "Metrado ejecutado"
        verbose_name_plural = "Metrados ejecutados"
        unique_together = ("avance", "partida")

    def __str__(self):
        return f"{self.partida.item}: {self.metrado_acumulado} {self.partida.unidad}"


class EvidenciaAvance(models.Model):
    """Evidencia fotográfica adjunta a un registro de avance (RF-15)."""

    avance = models.ForeignKey(AvanceObra, on_delete=models.CASCADE, related_name="evidencias")
    imagen = models.ImageField("Fotografía", upload_to="evidencias/%Y/%m/", validators=[validar_imagen])
    descripcion = models.CharField("Descripción", max_length=255, blank=True)
    fecha = models.DateTimeField("Fecha de carga", auto_now_add=True)

    class Meta:
        verbose_name = "Evidencia de avance"
        verbose_name_plural = "Evidencias de avance"
        ordering = ["-fecha"]

    def __str__(self):
        return f"Evidencia de {self.avance}"

    def save(self, *args, **kwargs):
        # RNF-08: se comprime la imagen antes de almacenarla para optimizar
        # el ancho de banda en condiciones de conectividad limitada.
        # comprimir_imagen ya conserva el original y deja constancia si no puede comprimirla.
        if self.imagen and hasattr(self.imagen, "file") and (self.pk is None or self._imagen_cambio()):
            self.imagen = comprimir_imagen(self.imagen)
        super().save(*args, **kwargs)

    def _imagen_cambio(self):
        if not self.pk:
            return True
        try:
            anterior = EvidenciaAvance.objects.get(pk=self.pk)
            return anterior.imagen != self.imagen
        except EvidenciaAvance.DoesNotExist:
            return True
