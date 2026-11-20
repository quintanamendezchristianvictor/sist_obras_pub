"""
Catálogo único de roles del sistema (RF-03), usado tanto por el modelo de
usuario (usuarios.models.Usuario) como por los mixins y decoradores de
control de acceso (core.mixins / core.decorators), para evitar definiciones
duplicadas o inconsistentes.
"""

# Actores definidos en el numeral 3.2 de la especificación de requisitos:
# - Administrador: personal de infraestructura que configura el sistema,
#   gestiona usuarios y roles y registra las obras.
# - Residente: registra avance físico/financiero, valorizaciones e incidencias.
# - Supervisor: revisa y valida los registros del residente, elabora su informe
#   mensual y hace seguimiento del calendario de ejecución.
# - Personal administrativo de apoyo: gestiona el acervo documentario y apoya
#   la consolidación de la información para reportes.
# - Alta dirección: consulta reportes consolidados y el dashboard.
ROL_ADMIN = "ADMIN"
ROL_APOYO = "APOYO"
ROL_RESIDENTE = "RESIDENTE"
ROL_SUPERVISOR = "SUPERVISOR"
ROL_ALTA_DIRECCION = "ALTA_DIRECCION"

ROLES_CHOICES = [
    (ROL_ADMIN, "Administrador del sistema"),
    (ROL_RESIDENTE, "Residente de obra"),
    (ROL_SUPERVISOR, "Supervisor / Inspector de obra"),
    (ROL_APOYO, "Personal administrativo de apoyo"),
    (ROL_ALTA_DIRECCION, "Alta dirección"),
]

# Grupos de roles usados con frecuencia para autorizar operaciones (RF-04)
ROLES_GESTION_OBRA = [ROL_ADMIN]
ROLES_CAMPO = [ROL_RESIDENTE, ROL_SUPERVISOR]
ROLES_TODOS = [c[0] for c in ROLES_CHOICES]

# Estados de obra (RF-08)
ESTADO_EN_EJECUCION = "EN_EJECUCION"
ESTADO_PARALIZADA = "PARALIZADA"
ESTADO_CONCLUIDA = "CONCLUIDA"
ESTADO_CON_RETRASO = "CON_RETRASO"

ESTADOS_OBRA_CHOICES = [
    (ESTADO_EN_EJECUCION, "En ejecución"),
    (ESTADO_PARALIZADA, "Paralizada"),
    (ESTADO_CONCLUIDA, "Concluida"),
    (ESTADO_CON_RETRASO, "Con retraso"),
]

# Modalidad de ejecución de obra (marco teórico 2.5.4.2 del plan de tesis)
MODALIDAD_CONTRATA = "CONTRATA"
MODALIDAD_ADMINISTRACION_DIRECTA = "ADMINISTRACION_DIRECTA"

MODALIDAD_EJECUCION_CHOICES = [
    (MODALIDAD_CONTRATA, "Ejecución por contrata"),
    (MODALIDAD_ADMINISTRACION_DIRECTA, "Ejecución por administración directa"),
]

# Unidades orgánicas que se sugieren al registrar una obra (RF-10, RF-30)
UNIDADES_ORGANICAS_SUGERIDAS = [
    "Subgerencia de Infraestructura",
    "Subgerencia de Desarrollo Social",
    "Subgerencia de Desarrollo Económico",
    "Subgerencia de Gestión Ambiental",
]

# Naturaleza de la obra que exige INFOBRAS (RF-28)
NATURALEZA_OBRA_CHOICES = [
    ("CONSTRUCCION", "Construcción"),
    ("MEJORAMIENTO", "Mejoramiento"),
    ("AMPLIACION", "Ampliación"),
    ("REHABILITACION", "Rehabilitación"),
    ("OTRA", "Otra"),
]

# Clasificación de desviación de avance (RF-14, RF-32)
SEMAFORO_A_TIEMPO = "A_TIEMPO"
SEMAFORO_EN_RIESGO = "EN_RIESGO"
SEMAFORO_ATRASADA = "ATRASADA"

SEMAFORO_CHOICES = [
    (SEMAFORO_A_TIEMPO, "A tiempo"),
    (SEMAFORO_EN_RIESGO, "En riesgo"),
    (SEMAFORO_ATRASADA, "Atrasada"),
]

SEMAFORO_COLOR = {
    SEMAFORO_A_TIEMPO: "success",
    SEMAFORO_EN_RIESGO: "warning",
    SEMAFORO_ATRASADA: "danger",
}
