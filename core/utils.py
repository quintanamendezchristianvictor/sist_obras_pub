"""
Utilidades compartidas por los distintos módulos del sistema.
"""

import io
import logging

from django.conf import settings
from django.core.files.base import ContentFile
from django.http import HttpResponse
from django.template.loader import render_to_string
from PIL import Image, ImageOps

from .pdf import html_a_pdf

logger = logging.getLogger(__name__)


def comprimir_imagen(imagen_django, nombre_salida=None):
    """
    Redimensiona y comprime una imagen subida por el usuario (evidencia
    fotográfica del avance de obra, RF-15) para reducir su peso antes de
    guardarla, en atención a las condiciones de conectividad limitada del
    distrito de Santa Rosa - Ayacucho (RNF-08).

    Recibe un archivo tipo InMemoryUploadedFile / TemporaryUploadedFile y
    devuelve un ContentFile en formato JPEG listo para asignarse a un
    ImageField.
    """
    try:
        imagen = Image.open(imagen_django)

        # Corrige la orientación según los metadatos EXIF de la cámara o el
        # celular con el que se tomó la evidencia en campo: sin esto, una
        # fotografía tomada en vertical puede terminar guardándose "acostada".
        imagen = ImageOps.exif_transpose(imagen)
        imagen = imagen.convert("RGB")

        # Límite por el lado mayor (no solo el ancho): una fotografía tomada
        # en vertical tiene el alto como lado mayor, y también debe limitarse.
        lado_max = getattr(settings, "EVIDENCIA_IMG_MAX_WIDTH", 1280)
        lado_mayor = max(imagen.width, imagen.height)
        if lado_mayor > lado_max:
            proporcion = lado_max / float(lado_mayor)
            nuevo_tamano = (
                max(1, round(imagen.width * proporcion)),
                max(1, round(imagen.height * proporcion)),
            )
            imagen = imagen.resize(nuevo_tamano, Image.Resampling.LANCZOS)

        buffer = io.BytesIO()
        calidad = getattr(settings, "EVIDENCIA_IMG_CALIDAD", 70)
        # JPEG progresivo: en una conexión lenta o intermitente (RNF-08) la
        # imagen se percibe completa antes, en vez de cargar de arriba hacia
        # abajo en una sola pasada.
        imagen.save(buffer, format="JPEG", quality=calidad, optimize=True, progressive=True)
        buffer.seek(0)

        nombre = nombre_salida or getattr(imagen_django, "name", "evidencia.jpg")
        if not nombre.lower().endswith(".jpg"):
            nombre = nombre.rsplit(".", 1)[0] + ".jpg"

        return ContentFile(buffer.read(), name=nombre)
    except Exception:
        # Si la compresión falla (archivo no soportado, etc.) se conserva el
        # archivo original para no bloquear el registro del avance, pero se
        # deja constancia en el log para poder diagnosticar el caso.
        logger.warning(
            "No se pudo comprimir la evidencia fotográfica '%s'; se conserva el archivo original.",
            getattr(imagen_django, "name", "?"),
            exc_info=True,
        )
        imagen_django.seek(0)
        return imagen_django


def calcular_semaforo(porcentaje_programado, porcentaje_ejecutado, umbral_riesgo=10, umbral_atraso=20):
    """
    Clasifica el estado de avance de una obra comparando lo programado contra
    lo ejecutado (RF-14). Devuelve una tupla (codigo_semaforo, desviacion).
    """
    from .constants import SEMAFORO_A_TIEMPO, SEMAFORO_ATRASADA, SEMAFORO_EN_RIESGO

    desviacion = float(porcentaje_programado or 0) - float(porcentaje_ejecutado or 0)

    if desviacion >= umbral_atraso:
        return SEMAFORO_ATRASADA, desviacion
    if desviacion >= umbral_riesgo:
        return SEMAFORO_EN_RIESGO, desviacion
    return SEMAFORO_A_TIEMPO, desviacion


def render_to_pdf(template_src, contexto, nombre_archivo="documento.pdf"):
    """
    Genera un PDF a partir de una plantilla Django (RF-18: exportación de
    valorizaciones e informes mensuales en PDF; RF-27: reportes consolidados
    en PDF). Usa xhtml2pdf por ser una librería 100% Python, sin
    dependencias externas del sistema operativo, lo que facilita su
    ejecución tanto en Windows (XAMPP) como en Linux.
    """
    contenido = html_a_pdf(render_to_string(template_src, contexto))
    if contenido is None:
        logger.error("xhtml2pdf no pudo generar %s desde %s", nombre_archivo, template_src)
        return HttpResponse("Ocurrió un error al generar el documento PDF.", status=500)
    return respuesta_pdf(contenido, nombre_archivo)


def respuesta_pdf(contenido, nombre_archivo):
    response = HttpResponse(contenido, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{nombre_archivo}"'
    return response
