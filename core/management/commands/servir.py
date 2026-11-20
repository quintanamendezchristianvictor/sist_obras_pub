"""
Servidor de producción para el despliegue en Windows o Linux (RNF-23).

    python manage.py collectstatic --noinput
    python manage.py servir --puerto 8000

Usa Waitress (100 % Python, sin dependencias nativas) en lugar de `runserver`,
que Django reserva para desarrollo.
"""

from django.core.management.base import BaseCommand
from django.core.wsgi import get_wsgi_application
from waitress import serve

from core.pdf import precalentar


class Command(BaseCommand):
    help = "Levanta el sistema con el servidor de producción Waitress (RNF-23)."

    def add_arguments(self, parser):
        parser.add_argument("--host", default="0.0.0.0", help="Interfaz de red (0.0.0.0 = toda la red local).")
        parser.add_argument("--puerto", type=int, default=8000)
        parser.add_argument("--hilos", type=int, default=12, help="Peticiones atendidas a la vez (RNF-07).")

    def handle(self, *args, **options):
        aplicacion = get_wsgi_application()
        precalentar()
        self.stdout.write(self.style.SUCCESS(f"Sistema disponible en el puerto {options['puerto']} ({options['hilos']} hilos)."))
        serve(aplicacion, host=options["host"], port=options["puerto"], threads=options["hilos"])
