"""
Pruebas unitarias del módulo de usuarios (RF-01 a RF-05).
"""

from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse

from core.constants import ROL_ADMIN, ROL_RESIDENTE

from .models import Usuario


class AutenticacionTests(TestCase):
    def setUp(self):
        self.usuario = Usuario.objects.create_user(
            username="u_test", password="Clave12345", rol=ROL_RESIDENTE, is_active=True
        )

    def test_login_correcto(self):
        response = self.client.post(reverse("usuarios:login"), {"username": "u_test", "password": "Clave12345"})
        self.assertEqual(response.status_code, 302)

    def test_login_incorrecto(self):
        response = self.client.post(reverse("usuarios:login"), {"username": "u_test", "password": "incorrecta"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "incorrect", status_code=200, html=False)

    def test_usuario_inactivo_no_puede_iniciar_sesion(self):
        self.usuario.is_active = False
        self.usuario.save()
        login_ok = self.client.login(username="u_test", password="Clave12345")
        self.assertFalse(login_ok)


class GestionUsuariosTests(TestCase):
    def setUp(self):
        self.admin = Usuario.objects.create_user(username="admin_u", password="Clave12345", rol=ROL_ADMIN)
        self.residente = Usuario.objects.create_user(username="res_u", password="Clave12345", rol=ROL_RESIDENTE)

    def test_solo_admin_ve_lista_usuarios(self):
        self.client.login(username="res_u", password="Clave12345")
        response = self.client.get(reverse("usuarios:lista"))
        self.assertEqual(response.status_code, 403)

        self.client.login(username="admin_u", password="Clave12345")
        response = self.client.get(reverse("usuarios:lista"))
        self.assertEqual(response.status_code, 200)

    def test_admin_no_puede_desactivar_su_propia_cuenta(self):
        self.client.login(username="admin_u", password="Clave12345")
        self.client.post(reverse("usuarios:toggle_activo", args=[self.admin.pk]))
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_active)

    def test_usuario_actualiza_sexo_y_ve_avatar_correspondiente(self):
        self.client.force_login(self.residente)
        response = self.client.post(
            reverse("usuarios:perfil"),
            {"first_name": "", "last_name": "", "email": "", "sexo": "F", "telefono": ""},
        )
        self.assertEqual(response.status_code, 302)
        self.residente.refresh_from_db()
        self.assertEqual(self.residente.sexo, "F")

        response = self.client.get(reverse("usuarios:perfil"))
        self.assertContains(response, "img/avatar-mujer.svg")


class SeguridadCuentasTests(TestCase):
    """RNF-17: bloqueo por intentos fallidos y protección de la propia cuenta de administrador."""

    def setUp(self):
        cache.clear()
        self.usuario = Usuario.objects.create_user(username="u_lock", password="Clave12345", rol=ROL_ADMIN)

    def _ingresar(self, clave):
        return self.client.post(reverse("usuarios:login"), {"username": "u_lock", "password": clave})

    @override_settings(LOGIN_INTENTOS_MAX=2)
    def test_bloquea_tras_intentos_fallidos_aun_con_la_clave_correcta(self):
        self._ingresar("mala")
        self._ingresar("mala")
        self.assertContains(self._ingresar("Clave12345"), "Demasiados intentos")

    def test_un_ingreso_correcto_reinicia_el_contador(self):
        self._ingresar("mala")
        self.assertEqual(self._ingresar("Clave12345").status_code, 302)
        self.assertFalse(cache.get("login_intentos:u_lock:127.0.0.1"))

    def test_administrador_no_puede_quitarse_el_rol_ni_desactivarse(self):
        self.client.force_login(self.usuario)
        respuesta = self.client.post(reverse("usuarios:editar", args=[self.usuario.pk]), {"rol": ROL_RESIDENTE, "first_name": "A"})
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn("rol", respuesta.context["form"].errors)
        self.assertIn("is_active", respuesta.context["form"].errors)
