from django.urls import path

from . import views

app_name = "reportes"

urlpatterns = [
    path("", views.DashboardView.as_view(), name="dashboard"),
    path("dashboard/data/", views.DashboardDataAPIView.as_view(), name="dashboard_data"),
    path("dashboard/firma/", views.DashboardFirmaAPIView.as_view(), name="dashboard_firma"),
    path("consolidado/pdf/", views.ReporteConsolidadoPDFView.as_view(), name="consolidado_pdf"),
    path("consolidado/excel/", views.ReporteConsolidadoExcelView.as_view(), name="consolidado_excel"),
]
