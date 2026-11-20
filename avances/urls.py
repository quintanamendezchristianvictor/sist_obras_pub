from django.urls import path

from . import views

app_name = "avances"

urlpatterns = [
    path("obra/<int:obra_pk>/", views.AvanceListView.as_view(), name="lista"),
    path("obra/<int:obra_pk>/nuevo/", views.AvanceCreateView.as_view(), name="crear"),
    path("<int:pk>/", views.AvanceDetailView.as_view(), name="detalle"),
    path("<int:pk>/corregir/", views.AvanceUpdateView.as_view(), name="editar"),
    path("<int:avance_pk>/evidencia/nueva/", views.EvidenciaCreateView.as_view(), name="evidencia_crear"),
]
