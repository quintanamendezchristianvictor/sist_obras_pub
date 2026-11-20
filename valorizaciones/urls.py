from django.urls import path

from . import views

app_name = "valorizaciones"

urlpatterns = [
    path("obra/<int:obra_pk>/", views.ValorizacionListView.as_view(), name="lista"),
    path("obra/<int:obra_pk>/nueva/", views.ValorizacionCreateView.as_view(), name="crear"),
    path("<int:pk>/revisar/", views.ValorizacionRevisarView.as_view(), name="revisar"),
    path("<int:pk>/subsanar/", views.ValorizacionSubsanarView.as_view(), name="subsanar"),
    path("<int:pk>/pdf/", views.ValorizacionExportarPDFView.as_view(), name="pdf"),

    path("obra/<int:obra_pk>/informes/", views.InformeMensualListView.as_view(), name="informes"),
    path("obra/<int:obra_pk>/informes/nuevo/", views.InformeMensualCreateView.as_view(), name="informe_crear"),
    path("informes/<int:pk>/", views.InformeMensualDetailView.as_view(), name="informe_detalle"),
    path("informes/<int:pk>/pdf/", views.InformeMensualExportarPDFView.as_view(), name="informe_pdf"),
]
