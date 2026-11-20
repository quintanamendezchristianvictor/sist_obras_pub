"""
Validación de los archivos que suben los usuarios (RNF-17, RNF-19): tipo y
tamaño máximo. Se aplican en los modelos, de modo que cualquier formulario
del sistema las reutiliza sin repetirlas.
"""

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator

EXTENSIONES_DOCUMENTO = ["pdf", "doc", "docx", "xls", "xlsx", "jpg", "jpeg", "png"]
EXTENSIONES_IMAGEN = ["jpg", "jpeg", "png", "webp"]


def _validar_tamano(archivo):
    limite = settings.SUBIDA_MAX_MB
    if archivo.size > limite * 1024 * 1024:
        raise ValidationError(f"El archivo supera el tamaño máximo permitido ({limite} MB).")


def _validar_contenido_pdf(archivo):
    """La extensión se puede cambiar a mano: se comprueba además la firma del archivo."""
    posicion = archivo.tell()
    archivo.seek(0)
    cabecera = archivo.read(5)
    archivo.seek(posicion)
    if cabecera != b"%PDF-":
        raise ValidationError("El archivo no es un PDF válido.")


def validar_documento(archivo):
    """Documentos del acervo y sustentos: PDF, Word, Excel o imagen."""
    FileExtensionValidator(EXTENSIONES_DOCUMENTO, "Tipo de archivo no permitido. Use: %(allowed_extensions)s.")(archivo)
    _validar_tamano(archivo)
    if archivo.name.lower().endswith(".pdf"):
        _validar_contenido_pdf(archivo)


def validar_pdf(archivo):
    """Expedientes técnicos y sustentos de valorización: solo PDF."""
    FileExtensionValidator(["pdf"], "Solo se admiten archivos PDF.")(archivo)
    _validar_tamano(archivo)
    _validar_contenido_pdf(archivo)


def validar_imagen(archivo):
    """Evidencias fotográficas. ImageField ya comprueba que el contenido sea una imagen real."""
    FileExtensionValidator(EXTENSIONES_IMAGEN, "Solo se admiten imágenes: %(allowed_extensions)s.")(archivo)
    _validar_tamano(archivo)
