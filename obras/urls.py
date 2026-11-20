from django.urls import path

from . import views

app_name = "obras"

urlpatterns = [
    path("", views.ObraListView.as_view(), name="lista"),
    path("nueva/", views.ObraCreateView.as_view(), name="crear"),
    path("<int:pk>/", views.ObraDetailView.as_view(), name="detalle"),
    path("<int:pk>/editar/", views.ObraUpdateView.as_view(), name="editar"),
    path("<int:obra_pk>/expediente/", views.ExpedienteTecnicoUpsertView.as_view(), name="expediente"),
    path("<int:obra_pk>/infobras/", views.FichaInfobrasUpsertView.as_view(), name="ficha_infobras"),
]
