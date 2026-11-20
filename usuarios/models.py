from django.contrib.auth.models import AbstractUser
from django.db import models

from core.constants import ROL_RESIDENTE, ROLES_CHOICES

SEXO_CHOICES = [
    ("M", "Varón"),
    ("F", "Mujer"),
]


class Usuario(AbstractUser):
    """
    Modelo de usuario personalizado del sistema (RF-01 a RF-05).

    Extiende AbstractUser (Django ya resuelve el cifrado de contraseñas con
    PBKDF2-SHA256, cumpliendo RNF-15) agregando el rol funcional del usuario
    dentro del proceso de control y seguimiento de obras (RF-03) y datos de
    contacto básicos del personal de la entidad.
    """

    rol = models.CharField("Rol", max_length=20, choices=ROLES_CHOICES, default=ROL_RESIDENTE)
    sexo = models.CharField("Sexo", max_length=1, choices=SEXO_CHOICES, blank=True, default="")
    dni = models.CharField("DNI", max_length=8, unique=True, null=True, blank=True)
    telefono = models.CharField("Teléfono", max_length=20, blank=True)
    cargo = models.CharField("Cargo", max_length=100, blank=True)
    unidad_organica = models.CharField("Unidad orgánica", max_length=150, blank=True)

    class Meta:
        verbose_name = "Usuario"
        verbose_name_plural = "Usuarios"
        ordering = ["first_name", "last_name"]

    def __str__(self):
        nombre = self.get_full_name()
        return f"{nombre} ({self.get_rol_display()})" if nombre else self.username

    @property
    def es_administrador(self):
        from core.constants import ROL_ADMIN

        return self.rol == ROL_ADMIN

    @property
    def es_residente(self):
        return self.rol == ROL_RESIDENTE

    @property
    def es_supervisor(self):
        from core.constants import ROL_SUPERVISOR

        return self.rol == ROL_SUPERVISOR

    @property
    def es_alta_direccion(self):
        from core.constants import ROL_ALTA_DIRECCION

        return self.rol == ROL_ALTA_DIRECCION
