from django.urls import path

from . import views

app_name = "usuarios"

urlpatterns = [
    path("login/", views.LoginView.as_view(), name="login"),
    path("logout/", views.LogoutView.as_view(), name="logout"),

    path("", views.UsuarioListView.as_view(), name="lista"),
    path("nuevo/", views.UsuarioCreateView.as_view(), name="crear"),
    path("<int:pk>/editar/", views.UsuarioUpdateView.as_view(), name="editar"),
    path("<int:pk>/activar-desactivar/", views.UsuarioToggleActivoView.as_view(), name="toggle_activo"),

    path("perfil/", views.PerfilUpdateView.as_view(), name="perfil"),
    path("perfil/cambiar-password/", views.CambiarPasswordView.as_view(), name="cambiar_password"),

    path("password/recuperar/", views.RecuperarPasswordView.as_view(), name="password_reset"),
    path("password/recuperar/enviado/", views.RecuperarPasswordDoneView.as_view(), name="password_reset_done"),
    path(
        "password/recuperar/confirmar/<uidb64>/<token>/",
        views.RecuperarPasswordConfirmView.as_view(),
        name="password_reset_confirm",
    ),
    path(
        "password/recuperar/completado/",
        views.RecuperarPasswordCompleteView.as_view(),
        name="password_reset_complete",
    ),
]
