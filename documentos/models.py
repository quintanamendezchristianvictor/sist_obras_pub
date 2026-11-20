from django.conf import settings
from django.db import models

from core.validators import validar_documento
from obras.models import Obra


class TipoDocumento(models.Model):
    """Catálogo de tipos de documento del acervo documentario (RF-25)."""

    nombre = models.CharField("Tipo de documento", max_length=100, unique=True)

    class Meta:
        verbose_name = "Tipo de documento"
        verbose_name_plural = "Tipos de documento"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class Documento(models.Model):
    """
    Documento digital del acervo documentario de una obra (RF-24 a RF-26):
    expediente técnico, actas, resoluciones, contratos, entre otros.
    """

    obra = models.ForeignKey(Obra, on_delete=models.CASCADE, related_name="documentos")
    tipo_documento = models.ForeignKey(TipoDocumento, on_delete=models.PROTECT, related_name="documentos")
    nombre = models.CharField("Nombre del documento", max_length=255)
    periodo = models.DateField("Periodo asociado", null=True, blank=True)
    descripcion = models.TextField("Descripción", blank=True)
    archivo = models.FileField("Archivo", upload_to="documentos/%Y/%m/", validators=[validar_documento])

    subido_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="documentos_subidos",
    )
    fecha_carga = models.DateTimeField("Fecha de carga", auto_now_add=True)

    class Meta:
        verbose_name = "Documento"
        verbose_name_plural = "Acervo documentario"
        ordering = ["-fecha_carga"]

    def __str__(self):
        return f"{self.nombre} ({self.tipo_documento})"

    @property
    def extension(self):
        return self.archivo.name.rsplit(".", 1)[-1].upper() if self.archivo else ""
