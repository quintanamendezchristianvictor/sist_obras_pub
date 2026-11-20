from datetime import date, timedelta
from decimal import Decimal

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q, Sum
from django.urls import reverse

from core.constants import (
    ESTADO_EN_EJECUCION,
    ESTADOS_OBRA_CHOICES,
    MODALIDAD_CONTRATA,
    MODALIDAD_EJECUCION_CHOICES,
    NATURALEZA_OBRA_CHOICES,
    ROL_RESIDENTE,
    ROL_SUPERVISOR,
)
from core.models import Configuracion
from core.utils import calcular_semaforo
from core.validators import validar_pdf


class Obra(models.Model):
    """
    Ficha técnica de una obra pública (RF-06 a RF-10).

    Constituye el eje central del dominio del sistema: todos los demás
    módulos (avances, valorizaciones, calendario, documentos) se relacionan
    con una obra registrada aquí.
    """

    codigo = models.CharField("Código / CUI", max_length=20, unique=True)
    nombre = models.CharField("Nombre de la obra", max_length=255)
    descripcion = models.TextField("Descripción", blank=True)

    # Ubicación
    direccion = models.CharField("Dirección / sector", max_length=255, blank=True)
    distrito = models.CharField("Distrito", max_length=100, default="Santa Rosa")
    provincia = models.CharField("Provincia", max_length=100, default="La Mar")
    departamento = models.CharField("Departamento", max_length=100, default="Ayacucho")

    # Datos técnicos y presupuestales (RF-06)
    modalidad_ejecucion = models.CharField(
        "Modalidad de ejecución", max_length=30,
        choices=MODALIDAD_EJECUCION_CHOICES, default=MODALIDAD_CONTRATA,
    )
    meta_fisica = models.CharField("Meta física", max_length=255)
    unidad_medida = models.CharField("Unidad de medida de la meta", max_length=50, blank=True)
    plazo_ejecucion_dias = models.PositiveIntegerField("Plazo de ejecución (días)")
    fecha_inicio = models.DateField("Fecha de inicio")
    fecha_fin_programada = models.DateField("Fecha de culminación programada")
    presupuesto_asignado = models.DecimalField("Presupuesto asignado (S/)", max_digits=14, decimal_places=2)

    # Contratista (solo ejecución por contrata; dato exigido por INFOBRAS, RF-28)
    contratista = models.CharField("Contratista", max_length=200, blank=True)
    contratista_ruc = models.CharField("RUC del contratista", max_length=11, blank=True)

    # Estado y responsables (RF-08, RF-09)
    estado = models.CharField("Estado de la obra", max_length=20, choices=ESTADOS_OBRA_CHOICES, default=ESTADO_EN_EJECUCION)
    unidad_organica = models.CharField(
        "Unidad orgánica responsable", max_length=150, default="Subgerencia de Infraestructura"
    )
    residente = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name="Residente de obra", on_delete=models.PROTECT,
        related_name="obras_como_residente", limit_choices_to={"rol": ROL_RESIDENTE}, null=True, blank=True,
    )
    supervisor = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name="Supervisor / Inspector", on_delete=models.PROTECT,
        related_name="obras_como_supervisor", limit_choices_to={"rol": ROL_SUPERVISOR}, null=True, blank=True,
    )

    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name="Registrado por", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="obras_registradas",
    )
    fecha_registro = models.DateTimeField("Fecha de registro", auto_now_add=True)
    fecha_actualizacion = models.DateTimeField("Última actualización", auto_now=True)

    class Meta:
        verbose_name = "Obra"
        verbose_name_plural = "Obras"
        ordering = ["-fecha_registro"]
        # Criterios de búsqueda y filtrado frecuentes (RF-10, RF-30, RNF-04)
        indexes = [
            models.Index(fields=["estado"]),
            models.Index(fields=["modalidad_ejecucion"]),
            models.Index(fields=["unidad_organica"]),
            models.Index(fields=["-fecha_registro"]),
        ]
        constraints = [
            models.CheckConstraint(condition=Q(presupuesto_asignado__gt=0), name="obra_presupuesto_positivo"),
            models.CheckConstraint(condition=Q(plazo_ejecucion_dias__gt=0), name="obra_plazo_positivo"),
            models.CheckConstraint(condition=Q(fecha_fin_programada__gt=models.F("fecha_inicio")), name="obra_fin_posterior_al_inicio"),
        ]

    def __str__(self):
        return f"{self.codigo} - {self.nombre}"

    def get_absolute_url(self):
        return reverse("obras:detalle", args=[self.pk])

    @classmethod
    def visibles_para(cls, usuario):
        """
        Obras que el usuario puede consultar según su rol (RF-04): el residente
        y el supervisor solo ven las obras bajo su responsabilidad; el resto de
        roles ve la totalidad. Lo usan la ficha de la obra, el dashboard y los
        reportes, para que todos apliquen la misma regla.
        """
        qs = cls.objects.select_related("residente", "supervisor").all()
        if usuario.rol == ROL_RESIDENTE:
            return qs.filter(residente=usuario)
        if usuario.rol == ROL_SUPERVISOR:
            return qs.filter(supervisor=usuario)
        return qs

    @classmethod
    def unidades_visibles(cls, usuario):
        """Unidades orgánicas de las obras visibles para el usuario, para los filtros (RF-10, RF-30)."""
        return (
            cls.visibles_para(usuario).select_related(None).order_by("unidad_organica")
            .values_list("unidad_organica", flat=True).distinct()
        )

    # --- Indicadores agregados (alimentan RF-13, RF-14 y el dashboard RF-29) ---

    @property
    def ultimo_avance(self):
        # Se memoriza en la instancia: la ficha y los reportes consultan varios
        # indicadores del mismo avance y no deben repetir la consulta (RNF-04).
        if not hasattr(self, "_ultimo_avance"):
            self._ultimo_avance = self.avances.order_by("-periodo").first()
        return self._ultimo_avance

    @property
    def avance_fisico_acumulado(self):
        ultimo = self.ultimo_avance
        return float(ultimo.avance_fisico_ejecutado_acum) if ultimo else 0.0

    @property
    def avance_fisico_programado_acumulado(self):
        ultimo = self.ultimo_avance
        return float(ultimo.avance_fisico_programado_acum) if ultimo else 0.0

    @property
    def avance_financiero_acumulado(self):
        ultimo = self.ultimo_avance
        return float(ultimo.avance_financiero_ejecutado_acum) if ultimo else 0.0

    @property
    def avance_financiero_programado_acumulado(self):
        ultimo = self.ultimo_avance
        return float(ultimo.avance_financiero_programado_acum) if ultimo else 0.0

    @property
    def estado_semaforo(self):
        config = Configuracion.actual()
        codigo, desviacion = calcular_semaforo(
            self.avance_fisico_programado_acumulado,
            self.avance_fisico_acumulado,
            config.umbral_riesgo,
            config.umbral_atraso,
        )
        return codigo, desviacion

    @property
    def dias_transcurridos(self):
        return max((date.today() - self.fecha_inicio).days, 0)

    @property
    def presupuesto_vigente(self):
        """Presupuesto asignado + adicionales aprobados - deductivos aprobados (RF-23)."""
        from calendario.models import ESTADO_APROBADO, TIPO_ADICIONAL, TIPO_DEDUCTIVO

        aprobados = self.adicionales_deductivos.filter(estado=ESTADO_APROBADO)
        adicionales = aprobados.filter(tipo=TIPO_ADICIONAL).aggregate(t=Sum("monto"))["t"] or Decimal("0")
        deductivos = aprobados.filter(tipo=TIPO_DEDUCTIVO).aggregate(t=Sum("monto"))["t"] or Decimal("0")
        return self.presupuesto_asignado + adicionales - deductivos

    @property
    def dias_ampliados(self):
        """Días otorgados en ampliaciones de plazo aprobadas (RF-21, RF-23)."""
        from calendario.models import ESTADO_APROBADA

        return self.ampliaciones_plazo.filter(estado=ESTADO_APROBADA).aggregate(
            t=Sum("dias_otorgados")
        )["t"] or 0

    @property
    def plazo_vigente_dias(self):
        """Plazo original + días otorgados en ampliaciones de plazo aprobadas (RF-23)."""
        return self.plazo_ejecucion_dias + self.dias_ampliados

    @property
    def fecha_fin_vigente(self):
        """Fecha de culminación programada desplazada por las ampliaciones aprobadas (RF-23)."""
        return self.fecha_fin_programada + timedelta(days=self.dias_ampliados)

    def programado_acumulado_al(self, periodo):
        """
        Avance físico y financiero programado acumulado (%) hasta el periodo
        indicado, según el calendario de ejecución valorizado (RF-14, RF-20).
        Devuelve None si la obra aún no tiene calendario registrado.
        """
        calendario = self.calendario.all()
        if not calendario.exists():
            return None
        acumulado = calendario.filter(periodo__lte=periodo).aggregate(
            fisico=Sum("avance_fisico_programado"), monto=Sum("monto_programado")
        )
        fisico = min(acumulado["fisico"] or Decimal("0"), Decimal("100"))
        presupuesto = self.presupuesto_vigente
        financiero = (acumulado["monto"] or Decimal("0")) * 100 / presupuesto if presupuesto else Decimal("0")
        return fisico.quantize(Decimal("0.01")), min(financiero, Decimal("100")).quantize(Decimal("0.01"))

    def actualizar_financiero_vigente(self):
        """
        Recalcula el avance financiero del último periodo sobre el presupuesto
        vigente cuando este cambia por un adicional o deductivo aprobado
        (RF-12, RF-23). Los periodos anteriores se conservan como se reportaron.
        """
        avance = self.avances.order_by("-periodo").first()
        presupuesto = self.presupuesto_vigente
        if avance is None or presupuesto <= 0:
            return
        if avance.monto_devengado_acum is not None:
            financiero = min(avance.monto_devengado_acum * 100 / presupuesto, Decimal("100"))
            avance.avance_financiero_ejecutado_acum = financiero.quantize(Decimal("0.01"))
        programado = self.programado_acumulado_al(avance.periodo)
        if programado:
            avance.avance_financiero_programado_acum = programado[1]
        avance.save(update_fields=["avance_financiero_ejecutado_acum", "avance_financiero_programado_acum"])


class ExpedienteTecnico(models.Model):
    """Expediente técnico aprobado vinculado a la obra (RF-07)."""

    obra = models.OneToOneField(Obra, on_delete=models.CASCADE, related_name="expediente_tecnico")
    numero_expediente = models.CharField("Número de expediente técnico", max_length=100)
    entidad_formuladora = models.CharField("Entidad formuladora", max_length=200, blank=True)
    fecha_aprobacion = models.DateField("Fecha de aprobación")
    monto_expediente = models.DecimalField("Monto del expediente técnico (S/)", max_digits=14, decimal_places=2)
    archivo = models.FileField("Archivo del expediente (PDF)", upload_to="expedientes/%Y/%m/", null=True, blank=True, validators=[validar_pdf])
    observaciones = models.TextField("Observaciones", blank=True)

    class Meta:
        verbose_name = "Expediente técnico"
        verbose_name_plural = "Expedientes técnicos"

    def __str__(self):
        return f"Expediente {self.numero_expediente} - {self.obra.nombre}"


class PartidaExpediente(models.Model):
    """
    Partida del presupuesto del expediente técnico con su metrado programado
    (RF-11). Cuando una obra tiene partidas registradas, el avance físico de
    cada periodo se calcula a partir de los metrados ejecutados, ponderados
    por su costo (metrado x precio unitario), en lugar de digitarse a mano.
    """

    expediente = models.ForeignKey(ExpedienteTecnico, on_delete=models.CASCADE, related_name="partidas")
    item = models.CharField("Ítem", max_length=20)
    descripcion = models.CharField("Descripción de la partida", max_length=255)
    unidad = models.CharField("Unidad", max_length=20)
    metrado = models.DecimalField("Metrado programado", max_digits=14, decimal_places=2)
    precio_unitario = models.DecimalField("Precio unitario (S/)", max_digits=14, decimal_places=2)

    class Meta:
        verbose_name = "Partida del expediente"
        verbose_name_plural = "Partidas del expediente"
        ordering = ["item"]
        unique_together = ("expediente", "item")

    def __str__(self):
        return f"{self.item} {self.descripcion} ({self.unidad})"

    @property
    def parcial(self):
        return self.metrado * self.precio_unitario


class FichaInfobras(models.Model):
    """
    Datos de la obra que exige INFOBRAS y que no se registran en otros módulos
    (RF-28; Directiva N.° 005-2023-CG/GMPL, numeral 7.4.1): datos generales,
    de ejecución y de cierre. Son opcionales porque se completan a lo largo de
    la vida de la obra.
    """

    obra = models.OneToOneField(Obra, on_delete=models.CASCADE, related_name="ficha_infobras")

    # Datos generales
    naturaleza = models.CharField("Naturaleza de la obra", max_length=20, choices=NATURALEZA_OBRA_CHOICES, blank=True)
    latitud = models.DecimalField(
        "Latitud", max_digits=9, decimal_places=6, null=True, blank=True,
        validators=[MinValueValidator(-90), MaxValueValidator(90)],
    )
    longitud = models.DecimalField(
        "Longitud", max_digits=9, decimal_places=6, null=True, blank=True,
        validators=[MinValueValidator(-180), MaxValueValidator(180)],
    )
    convenio = models.CharField("Convenio de ejecución", max_length=255, blank=True)

    # Ejecución física y financiera
    fecha_entrega_terreno = models.DateField("Fecha de entrega de terreno", null=True, blank=True)
    contrato_numero = models.CharField("N.° de contrato", max_length=60, blank=True)
    contrato_fecha = models.DateField("Fecha del contrato", null=True, blank=True)
    contrato_monto = models.DecimalField(
        "Monto del contrato (S/)", max_digits=14, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(0)],
    )
    adelanto_directo = models.DecimalField(
        "Adelanto directo (S/)", max_digits=14, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(0)],
    )
    adelanto_materiales = models.DecimalField(
        "Adelanto de materiales (S/)", max_digits=14, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(0)],
    )
    controversias = models.TextField("Controversias", blank=True)

    # Cierre
    recepcion_fecha = models.DateField("Fecha de recepción", null=True, blank=True)
    recepcion_acta = models.CharField("Acta de recepción", max_length=100, blank=True)
    liquidacion_fecha = models.DateField("Fecha de liquidación", null=True, blank=True)
    liquidacion_monto = models.DecimalField(
        "Monto de liquidación (S/)", max_digits=14, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(0)],
    )
    liquidacion_resolucion = models.CharField("Resolución de liquidación", max_length=100, blank=True)
    transferencia_entidad = models.CharField("Entidad receptora de la transferencia", max_length=200, blank=True)
    transferencia_fecha = models.DateField("Fecha de transferencia", null=True, blank=True)

    class Meta:
        verbose_name = "Ficha INFOBRAS"
        verbose_name_plural = "Fichas INFOBRAS"

    def __str__(self):
        return f"Ficha INFOBRAS de {self.obra.codigo}"


class ParalizacionObra(models.Model):
    """Periodo de paralización o suspensión de la obra, con su motivo (RF-28)."""

    obra = models.ForeignKey(Obra, on_delete=models.CASCADE, related_name="paralizaciones")
    fecha_inicio = models.DateField("Inicio")
    fecha_fin = models.DateField("Fin", null=True, blank=True, help_text="Vacío si continúa paralizada.")
    motivo = models.CharField("Motivo", max_length=255)

    class Meta:
        verbose_name = "Paralización de obra"
        verbose_name_plural = "Paralizaciones de obra"
        ordering = ["fecha_inicio"]
        constraints = [
            models.CheckConstraint(
                condition=Q(fecha_fin__isnull=True) | Q(fecha_fin__gte=models.F("fecha_inicio")),
                name="paralizacion_fin_no_anterior_al_inicio",
            ),
        ]

    def __str__(self):
        return f"{self.obra.codigo}: {self.motivo}"
