from django.conf import settings
from django.core.cache import cache
from django.db import models

_CLAVE_CONFIGURACION = "configuracion_sistema"


class Bitacora(models.Model):
    """
    Historial de operaciones críticas de cada usuario (RNF-16: trazabilidad /
    auditoría). Se alimenta automáticamente desde core.middleware.BitacoraMiddleware
    y, de forma puntual, desde señales (signals) de los modelos sensibles.
    """

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="bitacoras",
        verbose_name="Usuario",
    )
    accion = models.CharField("Acción", max_length=20)
    modulo = models.CharField("Módulo", max_length=100)
    detalle = models.CharField("Detalle", max_length=255, blank=True)
    ruta = models.CharField("Ruta", max_length=255, blank=True)
    direccion_ip = models.GenericIPAddressField("Dirección IP", null=True, blank=True)
    fecha = models.DateTimeField("Fecha y hora", auto_now_add=True)

    class Meta:
        verbose_name = "Registro de bitácora"
        verbose_name_plural = "Bitácora del sistema"
        ordering = ["-fecha"]
        indexes = [models.Index(fields=["-fecha"]), models.Index(fields=["usuario", "-fecha"]), models.Index(fields=["accion", "-fecha"])]

    def __str__(self):
        usuario = self.usuario.get_full_name() if self.usuario else "Anónimo"
        return f"[{self.fecha:%Y-%m-%d %H:%M}] {usuario} - {self.accion} ({self.modulo})"


class Configuracion(models.Model):
    """
    Parámetros generales del sistema editables desde el panel de administración,
    sin necesidad de modificar el código (RNF-21: mantenibilidad / arquitectura
    modular y configurable).
    """

    nombre_entidad = models.CharField(
        "Nombre de la entidad", max_length=200, default="Municipalidad Distrital de Santa Rosa - Ayacucho"
    )
    nombre_sistema = models.CharField(
        "Nombre del sistema",
        max_length=200,
        default="Sistema Web de Control y Seguimiento de Obras Públicas",
    )
    umbral_riesgo = models.PositiveIntegerField(
        "Umbral de desviación para obras en riesgo (%)", default=10
    )
    umbral_atraso = models.PositiveIntegerField(
        "Umbral de desviación para obras atrasadas (%)", default=20
    )

    class Meta:
        verbose_name = "Configuración del sistema"
        verbose_name_plural = "Configuración del sistema"

    def __str__(self):
        return self.nombre_sistema

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)
        cache.delete(_CLAVE_CONFIGURACION)

    @classmethod
    def actual(cls):
        """Se consulta en cada plantilla y semáforo: se guarda en caché para no repetir la consulta (RNF-04)."""
        return cache.get_or_set(
            _CLAVE_CONFIGURACION, lambda: cls.objects.get_or_create(pk=1)[0], settings.CONFIGURACION_CACHE_SEGUNDOS
        )
