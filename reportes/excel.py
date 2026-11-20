"""
Libro Excel del reporte consolidado con la estructura de la información que
exige INFOBRAS (RF-27, RF-28, RNF-20): datos generales, ejecución física y
financiera, y cierre, según el numeral 7.4.1 de la Directiva N.° 005-2023-CG/GMPL.
Cada hoja se llena con una sola consulta, sin importar el número de obras (RNF-05).
"""

import openpyxl
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter

from avances.models import AvanceObra
from calendario.models import AdicionalDeductivo, AmpliacionPlazo, CalendarioEjecucion
from obras.models import ExpedienteTecnico, FichaInfobras, ParalizacionObra

COLUMNAS_CONSOLIDADO = [
    "Código / CUI", "Nombre de la obra", "Distrito", "Provincia", "Departamento",
    "Modalidad de ejecución", "Contratista", "RUC del contratista", "Estado",
    "Unidad orgánica responsable", "Residente de obra", "Supervisor / Inspector",
    "Fecha de inicio", "Fecha de culminación programada", "Fecha de culminación vigente",
    "Plazo original (días)", "Ampliaciones de plazo aprobadas", "Plazo vigente (días)",
    "Presupuesto asignado (S/)", "Adicionales aprobados (S/)", "Deductivos aprobados (S/)",
    "Presupuesto vigente (S/)", "Monto valorizado aprobado (S/)", "Monto devengado acumulado (S/)",
    "Periodo del último avance",
    "Avance físico programado (%)", "Avance físico ejecutado (%)",
    "Avance financiero programado (%)", "Avance financiero ejecutado (%)",
    "Desviación física (pp)", "Estado de avance (semáforo)",
]

_RELLENO = PatternFill(start_color="1F4E78", end_color="1F4E78", fill_type="solid")
_FUENTE = Font(color="FFFFFF", bold=True)


def _fecha(valor, formato="%d/%m/%Y"):
    return valor.strftime(formato) if valor else ""


def _numero(valor):
    return float(valor) if valor is not None else None


def _hoja(libro, titulo, columnas, filas, activa=None):
    hoja = activa or libro.create_sheet()
    hoja.title = titulo
    hoja.append(columnas)
    for celda in hoja[1]:
        celda.fill = _RELLENO
        celda.font = _FUENTE
    for fila in filas:
        hoja.append(fila)
    for col in range(1, len(columnas) + 1):
        hoja.column_dimensions[get_column_letter(col)].width = 22
    hoja.freeze_panes = "B2"
    return hoja


def _fila_consolidado(fila):
    obra, avance = fila["obra"], fila["avance"]
    return [
        obra.codigo, obra.nombre, obra.distrito, obra.provincia, obra.departamento,
        obra.get_modalidad_ejecucion_display(), obra.contratista, obra.contratista_ruc,
        obra.get_estado_display(), obra.unidad_organica,
        obra.residente.get_full_name() if obra.residente else "",
        obra.supervisor.get_full_name() if obra.supervisor else "",
        _fecha(obra.fecha_inicio), _fecha(obra.fecha_fin_programada), _fecha(fila["fecha_fin_vigente"]),
        obra.plazo_ejecucion_dias, fila["ampliaciones_aprobadas"], fila["plazo_vigente"],
        float(obra.presupuesto_asignado), float(fila["adicionales_aprobados"]), float(fila["deductivos_aprobados"]),
        float(fila["presupuesto_vigente"]), float(fila["valorizado_aprobado"]), float(fila["monto_devengado"]),
        _fecha(avance.periodo, "%m/%Y") if avance else "",
        fila["fisico_programado"], fila["fisico_ejecutado"], fila["financiero_programado"], fila["financiero_ejecutado"],
        fila["desviacion"], fila["semaforo_display"],
    ]


def _filas_datos_generales(obras, codigos):
    expedientes = {e.obra_id: e for e in ExpedienteTecnico.objects.filter(obra__in=obras)}
    fichas = {f.obra_id: f for f in FichaInfobras.objects.filter(obra__in=obras)}
    for obra_id, codigo in codigos.items():
        e, f = expedientes.get(obra_id), fichas.get(obra_id)
        yield [
            codigo,
            f.get_naturaleza_display() if f else "", _numero(f.latitud) if f else None, _numero(f.longitud) if f else None,
            f.convenio if f else "",
            e.numero_expediente if e else "", e.entidad_formuladora if e else "",
            _fecha(e.fecha_aprobacion) if e else "", _numero(e.monto_expediente) if e else None,
            _fecha(f.fecha_entrega_terreno) if f else "",
            f.contrato_numero if f else "", _fecha(f.contrato_fecha) if f else "", _numero(f.contrato_monto) if f else None,
            _numero(f.adelanto_directo) if f else None, _numero(f.adelanto_materiales) if f else None,
            f.controversias if f else "",
        ]


def _filas_cierre(obras):
    for f in FichaInfobras.objects.filter(obra__in=obras).select_related("obra").order_by("obra__codigo"):
        yield [
            f.obra.codigo, _fecha(f.recepcion_fecha), f.recepcion_acta, _fecha(f.liquidacion_fecha), _numero(f.liquidacion_monto),
            f.liquidacion_resolucion, f.transferencia_entidad, _fecha(f.transferencia_fecha),
        ]


def _filas_avances(obras, corte):
    avances = AvanceObra.objects.filter(obra__in=obras).select_related("obra").order_by("obra__codigo", "periodo")
    if corte:
        avances = avances.filter(periodo__lte=corte)
    for a in avances:
        yield [
            a.obra.codigo, _fecha(a.periodo, "%m/%Y"), float(a.avance_fisico_programado_acum), float(a.avance_fisico_ejecutado_acum),
            float(a.avance_financiero_programado_acum), float(a.avance_financiero_ejecutado_acum), _numero(a.monto_devengado_acum), a.observaciones,
        ]


def _filas_calendario(obras):
    for c in CalendarioEjecucion.objects.filter(obra__in=obras).select_related("obra").order_by("obra__codigo", "periodo"):
        yield [c.obra.codigo, _fecha(c.periodo, "%m/%Y"), c.meta_programada, float(c.monto_programado), float(c.avance_fisico_programado)]


def _filas_modificaciones(obras):
    for a in AmpliacionPlazo.objects.filter(obra__in=obras).select_related("obra").order_by("obra__codigo", "numero"):
        yield [a.obra.codigo, "Ampliación de plazo", a.numero, a.get_estado_display(), _fecha(a.fecha_solicitud), _fecha(a.fecha_aprobacion),
               a.resolucion, a.dias_otorgados, None, a.motivo]
    for m in AdicionalDeductivo.objects.filter(obra__in=obras).select_related("obra").order_by("obra__codigo", "tipo", "numero"):
        yield [m.obra.codigo, m.get_tipo_display(), m.numero, m.get_estado_display(), _fecha(m.fecha_solicitud), _fecha(m.fecha_aprobacion),
               m.resolucion, None, float(m.monto), m.sustento]


def _filas_paralizaciones(obras):
    for p in ParalizacionObra.objects.filter(obra__in=obras).select_related("obra").order_by("obra__codigo", "fecha_inicio"):
        yield [p.obra.codigo, _fecha(p.fecha_inicio), _fecha(p.fecha_fin), p.motivo]


def construir_libro(filas, corte=None):
    """Crea el libro a partir de las filas de `reportes.services.indicadores_por_obra`."""
    obras = [f["obra"].pk for f in filas]
    codigos = {f["obra"].pk: f["obra"].codigo for f in filas}
    libro = openpyxl.Workbook()
    _hoja(libro, "Reporte consolidado INFOBRAS", COLUMNAS_CONSOLIDADO, [_fila_consolidado(f) for f in filas], activa=libro.active)
    _hoja(libro, "Datos generales y contrato", [
        "Código / CUI", "Naturaleza de la obra", "Latitud", "Longitud", "Convenio", "N.° de expediente técnico", "Entidad formuladora",
        "Fecha de aprobación del expediente", "Monto del expediente (S/)", "Entrega de terreno", "N.° de contrato", "Fecha del contrato",
        "Monto del contrato (S/)", "Adelanto directo (S/)", "Adelanto de materiales (S/)", "Controversias",
    ], _filas_datos_generales(obras, codigos))
    _hoja(libro, "Avances mensuales", [
        "Código / CUI", "Periodo", "Físico programado (%)", "Físico ejecutado (%)", "Financiero programado (%)",
        "Financiero ejecutado (%)", "Monto devengado acumulado (S/)", "Observaciones",
    ], _filas_avances(obras, corte))
    _hoja(libro, "Cronograma", ["Código / CUI", "Periodo", "Meta programada", "Monto programado (S/)", "Físico programado (%)"], _filas_calendario(obras))
    _hoja(libro, "Modificaciones", [
        "Código / CUI", "Tipo", "N.°", "Estado", "Fecha de solicitud", "Fecha de resolución", "N.° de resolución",
        "Días otorgados", "Monto (S/)", "Motivo o sustento",
    ], _filas_modificaciones(obras))
    _hoja(libro, "Paralizaciones", ["Código / CUI", "Inicio", "Fin", "Motivo"], _filas_paralizaciones(obras))
    _hoja(libro, "Cierre de obra", [
        "Código / CUI", "Fecha de recepción", "Acta de recepción", "Fecha de liquidación", "Monto de liquidación (S/)",
        "Resolución de liquidación", "Entidad receptora de la transferencia", "Fecha de transferencia",
    ], _filas_cierre(obras))
    return libro
