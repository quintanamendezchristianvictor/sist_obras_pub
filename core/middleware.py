import logging

from .models import Bitacora

logger = logging.getLogger(__name__)

# Rutas o prefijos que no se registran en la bitácora para no saturarla
# (archivos estáticos, multimedia, favicon, etc.)
_PREFIJOS_IGNORADOS = ("/static/", "/media/", "/favicon.ico")

# Mapa método HTTP -> acción legible
_ACCIONES = {
    "POST": "CREAR/ACTUALIZAR",
    "PUT": "ACTUALIZAR",
    "PATCH": "ACTUALIZAR",
    "DELETE": "ELIMINAR",
}


def _ip_cliente(request):
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


class BitacoraMiddleware:
    """
    Middleware que registra en la Bitácora (RNF-16) las operaciones críticas
    (creación, actualización o eliminación de información) realizadas por los
    usuarios autenticados del sistema. Una operación guardada termina en una
    redirección; un formulario rechazado responde 200 y no debe registrarse,
    porque no modificó nada.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        try:
            if (
                request.method in _ACCIONES
                and not request.path.startswith(_PREFIJOS_IGNORADOS)
                and getattr(request, "user", None)
                and request.user.is_authenticated
                and 300 <= response.status_code < 400
            ):
                modulo = request.resolver_match.app_name if request.resolver_match else "desconocido"
                vista = request.resolver_match.url_name if request.resolver_match else ""
                Bitacora.objects.create(
                    usuario=request.user,
                    accion=_ACCIONES[request.method],
                    modulo=modulo or "sistema",
                    detalle=vista,
                    ruta=request.path,
                    direccion_ip=_ip_cliente(request),
                )
        except Exception:
            # La bitácora nunca debe interrumpir la operación del usuario, pero el fallo debe quedar registrado.
            logger.exception("No se pudo registrar la operación en la bitácora: %s", request.path)

        return response
