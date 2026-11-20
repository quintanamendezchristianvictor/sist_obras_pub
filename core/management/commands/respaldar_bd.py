"""
Copia de respaldo de la base de datos (RNF-18).

    python manage.py respaldar_bd

Genera un archivo comprimido con la fecha y hora en el nombre dentro de
BACKUP_DIR y conserva solo las últimas BACKUP_CONSERVAR copias. Usa
mysqldump (incluido en XAMPP) y, si no está disponible, recurre a
`dumpdata` de Django, que no requiere herramientas externas.

Para que sea periódico se programa con el Programador de tareas de Windows
o con cron en Linux (ver README.md).
"""

import gzip
import io
import os
import re
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import connection


class Command(BaseCommand):
    help = "Genera una copia de respaldo comprimida de la base de datos (RNF-18)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--formato", choices=["auto", "sql", "json"], default="auto",
            help="sql = mysqldump, json = dumpdata de Django, auto = sql si está disponible.",
        )

    def handle(self, *args, **options):
        destino = Path(settings.BACKUP_DIR)
        if not destino.is_absolute():
            destino = Path(settings.BASE_DIR) / destino
        destino.mkdir(parents=True, exist_ok=True)

        marca = datetime.now().strftime("%Y%m%d_%H%M%S")
        nombre_bd = re.sub(r"[^A-Za-z0-9_-]", "", Path(str(connection.settings_dict["NAME"])).stem) or "bd"
        formato = options["formato"]
        usar_sql = formato == "sql" or (formato == "auto" and self._mysqldump_disponible())

        if usar_sql:
            archivo = destino / f"{nombre_bd}_{marca}.sql.gz"
            self._respaldo_sql(archivo)
        else:
            archivo = destino / f"{nombre_bd}_{marca}.json.gz"
            self._respaldo_json(archivo)

        self._rotar(destino)
        tamano = archivo.stat().st_size / 1024
        self.stdout.write(self.style.SUCCESS(f"Copia de respaldo generada: {archivo} ({tamano:,.1f} KB)"))

    def _mysqldump_disponible(self):
        return connection.vendor == "mysql" and shutil.which(settings.MYSQLDUMP_PATH) is not None

    def _respaldo_sql(self, archivo):
        if connection.vendor != "mysql":
            raise CommandError("El formato sql solo está disponible con MySQL/MariaDB.")
        bd = connection.settings_dict
        comando = [
            settings.MYSQLDUMP_PATH,
            f"--host={bd['HOST'] or '127.0.0.1'}",
            f"--port={bd['PORT'] or '3306'}",
            f"--user={bd['USER']}",
            "--single-transaction", "--routines", "--default-character-set=utf8mb4",
            bd["NAME"],
        ]
        # La contraseña se pasa por variable de entorno para que no quede en la lista de procesos
        entorno = {**os.environ, "MYSQL_PWD": bd["PASSWORD"] or ""}
        try:
            proceso = subprocess.run(comando, capture_output=True, env=entorno, check=False)
        except FileNotFoundError as error:
            raise CommandError(f"No se encontró mysqldump en '{settings.MYSQLDUMP_PATH}'. Configure MYSQLDUMP_PATH en .env.") from error
        if proceso.returncode != 0:
            raise CommandError(f"mysqldump terminó con error: {proceso.stderr.decode(errors='replace').strip()}")
        with gzip.open(archivo, "wb") as salida:
            salida.write(proceso.stdout)

    def _respaldo_json(self, archivo):
        buffer = io.StringIO()
        call_command(
            "dumpdata", exclude=["contenttypes", "auth.permission", "sessions"],
            natural_foreign=True, indent=1, stdout=buffer,
        )
        with gzip.open(archivo, "wt", encoding="utf-8") as salida:
            salida.write(buffer.getvalue())

    def _rotar(self, destino):
        copias = sorted(
            [p for p in destino.iterdir() if p.name.endswith((".sql.gz", ".json.gz"))],
            key=lambda p: p.stat().st_mtime, reverse=True,
        )
        for antigua in copias[settings.BACKUP_CONSERVAR:]:
            antigua.unlink()
            self.stdout.write(f"Copia antigua eliminada: {antigua.name}")
