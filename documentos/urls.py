from django.urls import path

from . import views

app_name = "documentos"

urlpatterns = [
    path("", views.DocumentoBuscarView.as_view(), name="buscar"),
    path("obra/<int:obra_pk>/", views.DocumentoListView.as_view(), name="lista"),
    path("obra/<int:obra_pk>/nuevo/", views.DocumentoCreateView.as_view(), name="crear"),
]
