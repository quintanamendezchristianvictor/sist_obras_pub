"""
URLs raíz del proyecto. Cada módulo funcional del sistema vive en su propia
app de Django con su propio archivo urls.py (arquitectura modular, RNF-21),
incluida aquí bajo un prefijo de ruta legible.
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path, re_path
from django.views.generic import RedirectView

from core.views import ArchivoProtegidoView

# Textos del panel /admin/ (en lugar de "Administración de Django")
admin.site.site_header = "Administración"
admin.site.site_title = "Administración"

urlpatterns = [
    path("admin/", admin.site.urls),

    path("", RedirectView.as_view(pattern_name="reportes:dashboard", permanent=False)),

    path("usuarios/", include("usuarios.urls")),
    path("obras/", include("obras.urls")),
    path("avances/", include("avances.urls")),
    path("valorizaciones/", include("valorizaciones.urls")),
    path("calendario/", include("calendario.urls")),
    path("documentos/", include("documentos.urls")),
    path("reportes/", include("reportes.urls")),
    path("sistema/", include("core.urls")),

    # Archivos subidos: solo para usuarios autenticados (RNF-17)
    re_path(r"^media/(?P<ruta>.+)$", ArchivoProtegidoView.as_view(), name="archivo_protegido"),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATICFILES_DIRS[0])
