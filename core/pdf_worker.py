"""
Conversión de HTML a PDF que se ejecuta en un proceso aparte (ver core.pdf).
No debe importar Django: los procesos de trabajo solo necesitan xhtml2pdf.
"""

import io
import time


def convertir(html):
    """Devuelve los bytes del PDF, o None si xhtml2pdf informó errores."""
    from xhtml2pdf import pisa

    salida = io.BytesIO()
    resultado = pisa.CreatePDF(src=html, dest=salida, encoding="utf-8")
    return None if resultado.err else salida.getvalue()


def cargar_libreria():
    """Inicializador del proceso: importar xhtml2pdf tarda varios segundos en el primer uso."""
    from xhtml2pdf import pisa  # noqa: F401


def esperar(segundos):
    """Tarea mínima para obligar a que se creen todos los procesos al iniciar el servidor."""
    time.sleep(segundos)
