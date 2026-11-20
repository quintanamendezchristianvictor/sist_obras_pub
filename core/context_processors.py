from .models import Configuracion


def datos_globales(request):
    """
    Pone a disposición de todas las plantillas los datos generales del
    sistema y de la entidad (nombre, umbrales de alerta, etc.) sin tener que
    pasarlos manualmente desde cada vista.
    """
    return {"configuracion": Configuracion.actual()}
