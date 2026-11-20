from django.urls import path

from . import views

app_name = "core"

urlpatterns = [
    path("bitacora/", views.BitacoraListView.as_view(), name="bitacora"),
]
