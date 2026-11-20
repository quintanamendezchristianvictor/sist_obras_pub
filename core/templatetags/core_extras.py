from django import template

register = template.Library()


@register.filter(name="moneda")
def moneda(valor):
    """Da formato de moneda en soles a un número: 1234.5 -> 'S/ 1,234.50'."""
    try:
        return f"S/ {float(valor):,.2f}"
    except (TypeError, ValueError):
        return "S/ 0.00"


@register.filter(name="porcentaje")
def porcentaje(valor, decimales=1):
    try:
        return f"{float(valor):.{int(decimales)}f}%"
    except (TypeError, ValueError):
        return "0.0%"


@register.filter(name="badge_semaforo")
def badge_semaforo(codigo):
    from core.constants import SEMAFORO_COLOR

    return SEMAFORO_COLOR.get(codigo, "secondary")


@register.filter(name="attr")
def attr(field, css):
    """Permite agregar clases/atributos a un campo de formulario desde la plantilla."""
    return field.as_widget(attrs={"class": css})


@register.filter(name="list_json")
def list_json(valor):
    """Convierte un iterable (p. ej. dict_keys) en lista para serializarlo con json_script."""
    return list(valor)
