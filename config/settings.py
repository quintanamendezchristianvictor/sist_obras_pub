"""
Configuración principal del proyecto Django.

Sistema web para el control y seguimiento de obras públicas y evaluación
de su calidad según la norma ISO/IEC 25010 - Municipalidad Distrital de
Santa Rosa - Ayacucho, 2026.

Arquitectura: Django (patrón MVT, equivalente al MVC clásico:
Modelo = models.py, Vista/Controlador = views.py, Plantilla = templates/*.html)
Base de datos: MySQL (compatible con el servidor incluido en XAMPP)
"""

import sys
from pathlib import Path

from decouple import Csv, config
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# Seguridad (RNF-15: contraseñas cifradas la gestiona Django por defecto con
# PBKDF2-SHA256; RNF-16: trazabilidad vía app "core" - modelo Bitacora)
# ---------------------------------------------------------------------------
DEBUG = config("DJANGO_DEBUG", default=False, cast=bool)
PRUEBAS = "test" in sys.argv

SECRET_KEY = config("DJANGO_SECRET_KEY", default="django-insecure-solo-para-desarrollo")
if not DEBUG and not PRUEBAS and SECRET_KEY.startswith("django-insecure-"):
    raise ImproperlyConfigured("En producción defina DJANGO_SECRET_KEY en el archivo .env.")

ALLOWED_HOSTS = config("DJANGO_ALLOWED_HOSTS", default="127.0.0.1,localhost", cast=Csv())

# ---------------------------------------------------------------------------
# Aplicaciones
# ---------------------------------------------------------------------------
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",

    # Terceros
    "widget_tweaks",

    # Aplicaciones propias del sistema (una app = un módulo funcional)
    "core",
    "usuarios",
    "obras",
    "avances",
    "valorizaciones",
    "calendario",
    "documentos",
    "reportes",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    # Comprime las respuestas HTML y JSON (RNF-08)
    "django.middleware.gzip.GZipMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    # Middleware propio: registra en la Bitácora las peticiones relevantes (RNF-16)
    "core.middleware.BitacoraMiddleware",
]

if not DEBUG and not PRUEBAS:
    # Sirve los estáticos en producción, comprimidos y con caché prolongada (RNF-08, RNF-23)
    MIDDLEWARE.insert(1, "whitenoise.middleware.WhiteNoiseMiddleware")

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "core.context_processors.datos_globales",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# ---------------------------------------------------------------------------
# Base de datos: MySQL (XAMPP). Ver archivo .env para credenciales.
# Por defecto apunta al MySQL de XAMPP: host=localhost, puerto=3306,
# usuario=root, contraseña vacía (configuración típica de XAMPP en Windows).
# ---------------------------------------------------------------------------
DATABASES = {
    "default": {
        # Backend MySQL de Django que además acepta el MariaDB 10.4 de XAMPP
        # (ver config/db_backend/base.py).
        "ENGINE": "config.db_backend",
        "NAME": config("DB_NAME", default="obras_db"),
        "USER": config("DB_USER", default="root"),
        "PASSWORD": config("DB_PASSWORD", default=""),
        "HOST": config("DB_HOST", default="127.0.0.1"),
        "PORT": config("DB_PORT", default="3306"),
        "OPTIONS": {
            "charset": "utf8mb4",
            "init_command": "SET sql_mode='STRICT_TRANS_TABLES'",
        },
        # Reutiliza las conexiones entre peticiones en lugar de abrir una por cada una (RNF-04, RNF-07)
        "CONN_MAX_AGE": config("DB_CONN_MAX_AGE", default=60, cast=int),
        "CONN_HEALTH_CHECKS": True,
    }
}

# ---------------------------------------------------------------------------
# Modelo de usuario personalizado (RF-01 a RF-05)
# ---------------------------------------------------------------------------
AUTH_USER_MODEL = "usuarios.Usuario"

# RNF-15: ver core.hashers. El segundo permite ingresar con las contraseñas ya
# registradas, que se actualizan solas al iniciar sesión.
PASSWORD_HASHERS = [
    "core.hashers.PBKDF2Hasher600k",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
]
if PRUEBAS:
    # Solo en pruebas unitarias: evita que cada usuario de prueba tarde más de 1 s
    PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

# Bloqueo temporal tras varios intentos fallidos de inicio de sesión (usuarios.forms.LoginForm)
LOGIN_INTENTOS_MAX = 5
LOGIN_BLOQUEO_SEGUNDOS = 15 * 60

SESSION_COOKIE_AGE = 8 * 60 * 60  # una jornada de trabajo
PASSWORD_RESET_TIMEOUT = 24 * 60 * 60

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 8}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LOGIN_URL = "usuarios:login"
LOGIN_REDIRECT_URL = "reportes:dashboard"
LOGOUT_REDIRECT_URL = "usuarios:login"

# ---------------------------------------------------------------------------
# Correo electrónico (RF-05: recuperación de contraseña por correo)
# En desarrollo (DEBUG=True) el correo se imprime en la consola del servidor
# por defecto, para poder probar la recuperación de contraseña sin depender
# de un servidor SMTP real. En producción, defina EMAIL_BACKEND=smtp y los
# datos de la cuenta de correo de la entidad en el archivo .env.
# ---------------------------------------------------------------------------
_EMAIL_BACKEND_POR_DEFECTO = (
    "django.core.mail.backends.console.EmailBackend"
    if DEBUG
    else "django.core.mail.backends.smtp.EmailBackend"
)
EMAIL_BACKEND = config("EMAIL_BACKEND", default=_EMAIL_BACKEND_POR_DEFECTO)
EMAIL_HOST = config("EMAIL_HOST", default="smtp.gmail.com")
EMAIL_PORT = config("EMAIL_PORT", default=587, cast=int)
EMAIL_USE_TLS = config("EMAIL_USE_TLS", default=True, cast=bool)
EMAIL_HOST_USER = config("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = config("EMAIL_HOST_PASSWORD", default="")
DEFAULT_FROM_EMAIL = config(
    "DEFAULT_FROM_EMAIL", default="Sistema de Obras Públicas <no-reply@santarosa.gob.pe>"
)

# ---------------------------------------------------------------------------
# Internacionalización
# ---------------------------------------------------------------------------
LANGUAGE_CODE = "es-pe"
TIME_ZONE = "America/Lima"
USE_I18N = True
FORMAT_MODULE_PATH = "config.formats"
USE_TZ = True

# ---------------------------------------------------------------------------
# Archivos estáticos y multimedia (evidencias fotográficas, documentos, PDFs)
# ---------------------------------------------------------------------------
STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
if not DEBUG and not PRUEBAS:
    # Requiere `python manage.py collectstatic`
    STORAGES = {
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "core.storage.EstaticosProduccion"},
    }

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---------------------------------------------------------------------------
# Subida de archivos: límites razonables para evidencias y documentos
# (apoya RNF-08: optimización de ancho de banda en conexión limitada)
# ---------------------------------------------------------------------------
SUBIDA_MAX_MB = config("SUBIDA_MAX_MB", default=20, cast=int)  # tamaño máximo por archivo (core.validators)
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024  # datos de formulario, sin contar archivos

# Lado máximo (el mayor entre ancho y alto, en px) al que se recomprimen las
# imágenes de evidencia (RNF-08); así una fotografía tomada en vertical desde
# el celular se limita igual que una tomada en horizontal.
EVIDENCIA_IMG_MAX_WIDTH = 1280
EVIDENCIA_IMG_CALIDAD = 70

# ---------------------------------------------------------------------------
# Parámetros propios del dominio del sistema
# ---------------------------------------------------------------------------
# Los umbrales de desviación del semáforo (RF-14, RF-32) no se definen aquí:
# se editan desde el panel de administración en core.models.Configuracion.

# Paginación por defecto en listados (apoya RNF-04/RNF-07: eficiencia de
# desempeño con grandes volúmenes de datos)
PAGINACION_POR_DEFECTO = 15

# ---------------------------------------------------------------------------
# Copias de respaldo de la base de datos (RNF-18): comando `respaldar_bd`
# ---------------------------------------------------------------------------
BACKUP_DIR = config("BACKUP_DIR", default=str(BASE_DIR / "backups"))
BACKUP_CONSERVAR = config("BACKUP_CONSERVAR", default=15, cast=int)  # n.° de copias que se conservan
# Ruta de mysqldump (en XAMPP para Windows: C:\xampp\mysql\bin\mysqldump.exe)
MYSQLDUMP_PATH = config("MYSQLDUMP_PATH", default="mysqldump")

# ---------------------------------------------------------------------------
# Caché: indicadores poco cambiantes, reportes ya generados e intentos de ingreso
# ---------------------------------------------------------------------------
CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "sigop"}}
CONFIGURACION_CACHE_SEGUNDOS = 0 if PRUEBAS else 300
REPORTE_PDF_CACHE_SEGUNDOS = 0 if PRUEBAS else 300

# ---------------------------------------------------------------------------
# Generación de PDF en procesos aparte (core.pdf; 0 = en el mismo proceso)
# ---------------------------------------------------------------------------
PDF_PROCESOS = config("PDF_PROCESOS", default=0 if DEBUG or PRUEBAS else 2, cast=int)

# ---------------------------------------------------------------------------
# Seguridad con HTTPS: DJANGO_HTTPS=True cuando el sitio se publique con certificado
# ---------------------------------------------------------------------------
if config("DJANGO_HTTPS", default=False, cast=bool):
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

# ---------------------------------------------------------------------------
# Registro de errores en logs/sistema.log (RNF-19, RNF-22)
# ---------------------------------------------------------------------------
(BASE_DIR / "logs").mkdir(exist_ok=True)
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"simple": {"format": "%(asctime)s %(levelname)s %(name)s: %(message)s"}},
    "handlers": {
        "consola": {"class": "logging.StreamHandler", "formatter": "simple"},
        "archivo": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": BASE_DIR / "logs" / "sistema.log",
            "maxBytes": 5 * 1024 * 1024,
            "backupCount": 5,
            "encoding": "utf-8",
            "delay": True,
        },
    },
    "root": {"handlers": ["consola"] if PRUEBAS else ["consola", "archivo"], "level": "WARNING"},
    # Evita el rastreo completo por cada 403/404, que es un resultado normal del control de acceso
    "loggers": {"django.request": {"level": "ERROR"}, "xhtml2pdf": {"level": "ERROR"}},
}

# ---------------------------------------------------------------------------
# Sesiones / mensajes
# ---------------------------------------------------------------------------
MESSAGE_TAGS = {
    10: "info",      # DEBUG
    20: "info",      # INFO
    25: "success",   # SUCCESS
    30: "warning",   # WARNING
    40: "danger",    # ERROR
}
