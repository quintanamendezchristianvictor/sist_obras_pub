"""
Generación de PDF sin bloquear al resto de usuarios (RNF-05, RNF-07).

xhtml2pdf usa intensivamente la CPU y, dentro del proceso del servidor, retiene
el GIL de Python: mientras se genera un reporte, las demás peticiones esperan.
Por eso la conversión se hace en procesos aparte (PDF_PROCESOS). Con
PDF_PROCESOS = 0 (desarrollo y pruebas) se convierte en el mismo proceso.
"""

import logging
import threading
from concurrent.futures import ProcessPoolExecutor, wait
from concurrent.futures.process import BrokenProcessPool

from django.conf import settings

from . import pdf_worker

logger = logging.getLogger(__name__)
_pool = None
_cerrojo = threading.Lock()


def _obtener_pool():
    global _pool
    if settings.PDF_PROCESOS < 1:
        return None
    with _cerrojo:
        if _pool is None:
            _pool = ProcessPoolExecutor(max_workers=settings.PDF_PROCESOS, initializer=pdf_worker.cargar_libreria)
        return _pool


def _descartar_pool():
    global _pool
    with _cerrojo:
        _pool = None


def precalentar():
    """Crea los procesos al iniciar el servidor para que el primer reporte no pague su arranque."""
    pool = _obtener_pool()
    if pool is not None:
        wait([pool.submit(pdf_worker.esperar, 1) for _ in range(settings.PDF_PROCESOS)])


def html_a_pdf(html):
    """Convierte el HTML en bytes de PDF; devuelve None si la conversión falla."""
    pool = _obtener_pool()
    if pool is None:
        return pdf_worker.convertir(html)
    try:
        return pool.submit(pdf_worker.convertir, html).result()
    except BrokenProcessPool:
        logger.exception("Falló el proceso de generación de PDF; se reintenta en el proceso principal.")
        _descartar_pool()
        return pdf_worker.convertir(html)
