from django.urls import path

from . import views

app_name = "calendario"

urlpatterns = [
    path("obra/<int:obra_pk>/", views.CalendarioEjecucionListView.as_view(), name="lista"),
    path("obra/<int:obra_pk>/nuevo/", views.CalendarioEjecucionCreateView.as_view(), name="crear"),
    path("obra/<int:obra_pk>/<int:pk>/editar/", views.CalendarioEjecucionUpdateView.as_view(), name="editar"),

    path("obra/<int:obra_pk>/ampliaciones/", views.AmpliacionPlazoListView.as_view(), name="ampliaciones"),
    path("obra/<int:obra_pk>/ampliaciones/nueva/", views.AmpliacionPlazoCreateView.as_view(), name="ampliacion_crear"),
    path("obra/<int:obra_pk>/ampliaciones/<int:pk>/resolver/", views.AmpliacionPlazoResolverView.as_view(), name="ampliacion_resolver"),

    path("obra/<int:obra_pk>/adicionales/", views.AdicionalDeductivoListView.as_view(), name="adicionales"),
    path("obra/<int:obra_pk>/adicionales/nuevo/", views.AdicionalDeductivoCreateView.as_view(), name="adicional_crear"),
    path("obra/<int:obra_pk>/adicionales/<int:pk>/resolver/", views.AdicionalDeductivoResolverView.as_view(), name="adicional_resolver"),
]
