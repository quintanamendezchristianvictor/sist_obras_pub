"""
Lógica de agregación de datos para el dashboard dinámico y los reportes
consolidados (RF-27 a RF-32). Se aísla en este módulo de servicios para que
tanto la vista HTML del dashboard como su endpoint JSON (usado por el
JavaScript del panel para refrescar los gráficos sin recargar la página,
RF-31) y los reportes PDF/Excel reutilicen exactamente la misma lógica de
cálculo.

Eficiencia (RNF-04, RNF-05, RNF-06): los indicadores de todas las obras se
obtienen con un número fijo de consultas (avances, sumas de modificaciones
aprobadas y de valorizaciones, todas agregadas en la base de datos), en
lugar de varias consultas por cada obra.
"""

from collections import defaultdict
from datetime import datetime, timedelta
from decimal import Decimal

from django.db.models import Count, DecimalField, IntegerField, Max, OuterRef, Subquery, Sum, Value
from django.db.models.functions import Coalesce

from avances.models import AvanceObra, asignar_ultimos_avances
from calendario.models import (
    ESTADO_APROBADA,
    ESTADO_APROBADO,
    TIPO_ADICIONAL,
    TIPO_DEDUCTIVO,
    AdicionalDeductivo,
    AmpliacionPlazo,
)
from core.constants import (
    ESTADO_CON_RETRASO,
    ESTADO_CONCLUIDA,
    ESTADO_EN_EJECUCION,
    ESTADO_PARALIZADA,
    SEMAFORO_ATRASADA,
    SEMAFORO_CHOICES,
    SEMAFORO_EN_RIESGO,
)
from core.models import Bitacora, Configuracion
from core.utils import calcular_semaforo
from obras.models import Obra
from valorizaciones.models import ESTADO_APROBADA as VALORIZACION_APROBADA
from valorizaciones.models import Valorizacion

_CERO = Decimal("0")
_SEMAFORO_LEGIBLE = dict(SEMAFORO_CHOICES)

# Meses que abarca como máximo la curva de evolución del dashboard (RF-31)
MESES_EVOLUCION = 24


def leer_periodo(request):
    """
    Periodo de corte (RF-30) en formato AAAA-MM. Devuelve el primer día del
    mes, o None si no se filtra por periodo (situación a la fecha).
    """
    valor = request.GET.get("periodo", "").strip()
    try:
        return datetime.strptime(valor, "%Y-%m").date()
    except ValueError:
        return None


def aplicar_filtros(request):
    """
    Aplica los filtros del dashboard dinámico (RF-30): obra, estado y unidad
    orgánica, partiendo solo de las obras visibles para el rol del usuario
    (RF-04). El filtro por periodo se aplica sobre los avances (ver
    `indicadores_por_obra`); además excluye las obras que aún no habían
    iniciado en ese periodo.
    """
    qs = Obra.visibles_para(request.user)

    obra_id = request.GET.get("obra", "").strip()
    estado = request.GET.get("estado", "").strip()
    unidad = request.GET.get("unidad", "").strip()
    periodo = leer_periodo(request)

    if obra_id.isdigit():
        qs = qs.filter(pk=obra_id)
    if estado:
        qs = qs.filter(estado=estado)
    if unidad:
        qs = qs.filter(unidad_organica__icontains=unidad)
    if periodo:
        qs = qs.filter(fecha_inicio__lt=_mes_siguiente(periodo))

    return qs


def _mes_siguiente(periodo):
    return (periodo.replace(day=1) + timedelta(days=32)).replace(day=1)


def _subconsulta(modelo, filtro, agregado):
    """Subconsulta con un agregado sobre los registros de la obra que cumplen `filtro`."""
    return Subquery(
        modelo.objects.filter(obra=OuterRef("pk"), **filtro).values("obra").annotate(valor=agregado).values("valor")
    )


def _suma_montos(modelo, filtro):
    return Coalesce(_subconsulta(modelo, filtro, Sum("monto")), Value(_CERO), output_field=DecimalField())


def _entero(modelo, filtro, agregado):
    return Coalesce(_subconsulta(modelo, filtro, agregado), Value(0), output_field=IntegerField())


def anotar_indicadores(qs):
    """Agrega a cada obra, con subconsultas, los montos y plazos derivados de sus modificaciones (RF-23)."""
    return qs.annotate(
        _adicionales=_suma_montos(AdicionalDeductivo, {"tipo": TIPO_ADICIONAL, "estado": ESTADO_APROBADO}),
        _deductivos=_suma_montos(AdicionalDeductivo, {"tipo": TIPO_DEDUCTIVO, "estado": ESTADO_APROBADO}),
        _dias_ampliados=_entero(AmpliacionPlazo, {"estado": ESTADO_APROBADA}, Sum("dias_otorgados")),
        _ampliaciones_aprobadas=_entero(AmpliacionPlazo, {"estado": ESTADO_APROBADA}, Count("pk")),
        _valorizado_aprobado=_suma_montos(Valorizacion, {"estado": VALORIZACION_APROBADA}),
    )


def indicadores_por_obra(obras_qs, corte=None):
    """
    Indicadores de avance, semáforo y montos/plazos vigentes de cada obra
    (RF-13, RF-14, RF-23, RF-27, RF-28), calculados con un número fijo de
    consultas. Devuelve una lista de diccionarios, en el orden del queryset.
    """
    config = Configuracion.actual()
    obras = list(anotar_indicadores(obras_qs))
    ultimos = asignar_ultimos_avances(obras, corte)

    filas = []
    for obra in obras:
        avance = ultimos.get(obra.pk)
        fisico_prog = float(avance.avance_fisico_programado_acum) if avance else 0.0
        fisico_ejec = float(avance.avance_fisico_ejecutado_acum) if avance else 0.0
        fin_prog = float(avance.avance_financiero_programado_acum) if avance else 0.0
        fin_ejec = float(avance.avance_financiero_ejecutado_acum) if avance else 0.0
        semaforo, desviacion = calcular_semaforo(fisico_prog, fisico_ejec, config.umbral_riesgo, config.umbral_atraso)
        filas.append({
            "obra": obra,
            "avance": avance,
            "fisico_programado": round(fisico_prog, 2),
            "fisico_ejecutado": round(fisico_ejec, 2),
            "financiero_programado": round(fin_prog, 2),
            "financiero_ejecutado": round(fin_ejec, 2),
            "desviacion": round(desviacion, 2),
            "semaforo": semaforo,
            "semaforo_display": _SEMAFORO_LEGIBLE.get(semaforo, ""),
            "presupuesto_vigente": obra.presupuesto_asignado + obra._adicionales - obra._deductivos,
            "adicionales_aprobados": obra._adicionales,
            "deductivos_aprobados": obra._deductivos,
            "plazo_vigente": obra.plazo_ejecucion_dias + obra._dias_ampliados,
            "fecha_fin_vigente": obra.fecha_fin_programada + timedelta(days=obra._dias_ampliados),
            "ampliaciones_aprobadas": obra._ampliaciones_aprobadas,
            "valorizado_aprobado": obra._valorizado_aprobado,
            "monto_devengado": (avance.monto_devengado_acum if avance else None) or _CERO,
        })
    return filas


def _serie_evolucion(obras, corte=None):
    """
    Curva de avance físico y financiero, programado vs. ejecutado, en el
    tiempo (RF-31): para cada mes, promedio de las obras que ya tenían algún
    avance registrado (si se filtra una sola obra, es su propia "curva S").
    """
    series = ("programado", "ejecutado", "financiero_programado", "financiero_ejecutado")
    avances = AvanceObra.objects.filter(obra__in=[o.pk for o in obras])
    if corte:
        avances = avances.filter(periodo__lte=corte)
    avances = list(avances.order_by("periodo").values_list("obra_id", "periodo",
                                                           "avance_fisico_programado_acum",
                                                           "avance_fisico_ejecutado_acum",
                                                           "avance_financiero_programado_acum",
                                                           "avance_financiero_ejecutado_acum"))
    if not avances:
        return {"etiquetas": [], **{serie: [] for serie in series}}

    por_mes = defaultdict(dict)
    for obra_id, periodo, *valores in avances:
        por_mes[periodo][obra_id] = [float(v) for v in valores]

    vigentes = {}  # último valor conocido de cada obra (se arrastra a los meses sin registro)
    etiquetas, valores_por_serie = [], {serie: [] for serie in series}
    for mes in sorted(por_mes):
        vigentes.update(por_mes[mes])
        etiquetas.append(mes.strftime("%m/%Y"))
        for i, serie in enumerate(series):
            valores_por_serie[serie].append(round(sum(v[i] for v in vigentes.values()) / len(vigentes), 1))
    return {
        "etiquetas": etiquetas[-MESES_EVOLUCION:],
        **{serie: valores[-MESES_EVOLUCION:] for serie, valores in valores_por_serie.items()},
    }


def firma_de_datos():
    """
    Identificador que cambia cada vez que alguien registra o modifica
    información (RF-31). Toda operación de escritura queda en la bitácora
    (RNF-16), así que basta con el último id registrado en ella. Es una
    consulta mínima, apta para que el dashboard la consulte con frecuencia
    sin consumir ancho de banda (RNF-08).
    """
    return Bitacora.objects.aggregate(ultimo=Max("id"))["ultimo"] or 0


def construir_datos_dashboard(request):
    """
    Calcula los indicadores clave (KPI) y los datos de los gráficos del
    dashboard dinámico (RF-29, RF-31, RF-32), aplicando los filtros vigentes
    (RF-30).
    """
    config = Configuracion.actual()
    corte = leer_periodo(request)
    filas = indicadores_por_obra(aplicar_filtros(request), corte)

    conteo_estados = {
        ESTADO_EN_EJECUCION: 0,
        ESTADO_PARALIZADA: 0,
        ESTADO_CONCLUIDA: 0,
        ESTADO_CON_RETRASO: 0,
    }
    obras_en_riesgo = []
    con_avance = [f for f in filas if f["avance"]]

    for fila in filas:
        obra = fila["obra"]
        conteo_estados[obra.estado] = conteo_estados.get(obra.estado, 0) + 1
        # Una obra concluida ya no puede estar en riesgo ni atrasada (RF-32)
        if obra.estado != ESTADO_CONCLUIDA and fila["semaforo"] in (SEMAFORO_EN_RIESGO, SEMAFORO_ATRASADA):
            obras_en_riesgo.append({
                "id": obra.pk,
                "codigo": obra.codigo,
                "nombre": obra.nombre,
                "estado": obra.get_estado_display(),
                "semaforo": fila["semaforo"],
                "semaforo_display": fila["semaforo_display"],
                "desviacion": round(fila["desviacion"], 1),
                "avance_fisico": round(fila["fisico_ejecutado"], 1),
            })

    def promedio(clave):
        return round(sum(f[clave] for f in con_avance) / len(con_avance), 1) if con_avance else 0

    # Ordenar obras en riesgo por mayor desviación primero
    obras_en_riesgo.sort(key=lambda o: o["desviacion"], reverse=True)

    return {
        "total_obras": len(filas),
        "conteo_estados": conteo_estados,
        "promedio_fisico_programado": promedio("fisico_programado"),
        "promedio_fisico_ejecutado": promedio("fisico_ejecutado"),
        "promedio_financiero_programado": promedio("financiero_programado"),
        "promedio_financiero_ejecutado": promedio("financiero_ejecutado"),
        "obras_en_riesgo": obras_en_riesgo,
        "total_en_riesgo": len(obras_en_riesgo),
        "umbral_riesgo": config.umbral_riesgo,
        "umbral_atraso": config.umbral_atraso,
        "periodo": corte.strftime("%m/%Y") if corte else "",
        "firma": firma_de_datos(),
        "graficos": {
            "etiquetas_obras": [f["obra"].codigo for f in filas],
            "fisico_programado": [round(f["fisico_programado"], 1) for f in filas],
            "fisico_ejecutado": [round(f["fisico_ejecutado"], 1) for f in filas],
            "financiero_programado": [round(f["financiero_programado"], 1) for f in filas],
            "financiero_ejecutado": [round(f["financiero_ejecutado"], 1) for f in filas],
            "semaforos": [f["semaforo"] for f in filas],
            "evolucion": _serie_evolucion([f["obra"] for f in filas], corte),
            "estados": {
                "etiquetas": ["En ejecución", "Paralizada", "Concluida", "Con retraso"],
                "valores": [
                    conteo_estados[ESTADO_EN_EJECUCION],
                    conteo_estados[ESTADO_PARALIZADA],
                    conteo_estados[ESTADO_CONCLUIDA],
                    conteo_estados[ESTADO_CON_RETRASO],
                ],
            },
        },
    }
